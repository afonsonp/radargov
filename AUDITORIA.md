# Auditoria completa ao Radar — 30 de agosto de 2026

Inventário e avaliação do que existe hoje, feito por leitura integral do
código (`radar.py`, 9 938 linhas; `teste_radar.py`, 3 230; hooks, skills
e `.bat`), da documentação (`ESTADO.md`, `CONCORRENTES.md`, `BACKLOG.md`,
`LEIA-ME.md`, `CLAUDE.md`) e por consulta às duas bases em modo
só-leitura. Nada foi alterado. Os números de linhas e contagens são desta
data; as medições de tempo citadas vêm do `ESTADO.md` e estão marcadas
como tal.

---

## Resumo executivo

O sistema **funciona e está em produção real**: recolha automática às
09:00/17:00 confirmada (slots de 28–30/08 corridos à hora certa, tarefas
do Windows criadas e "Ready"), 66 081 anúncios de dois anos, 1 363 300
contratos de 2020–2026, 405 testes verdes em 0,26 s, e as decisões de
desenho difíceis (identidade por NIF, um só motor de filtros, filas para
trabalho longo, migrações idempotentes) estão implementadas com
consistência invulgar para um ficheiro único de ~10 mil linhas. O código
está densamente comentado com o *porquê* de cada decisão, o que vale
tanto como a documentação externa.

Os problemas encontrados não são de arquitectura — são de **estado dos
dados, de documentação a mentir, e de dependências de um único PC**.

### Os 5 problemas mais urgentes

1. **A documentação de entrada está errada nos números que mais importam.**
   O `ESTADO.md` — que o `CLAUDE.md` manda ler antes de mexer — abre com
   «a base tem ~5100 anúncios, **todos com detalhe lido**, a cobrir os
   últimos 60 dias». A base real tem **66 081 anúncios de dois anos, com
   8,3 % de detalhes lidos** (5 493). O `LEIA-ME.md` §14 diz que «o radar
   lê o anúncio, não as peças do procedimento» — falso desde que
   `obter_documentos()`/`analisar_pecas()` existem — e §12 fala em «82
   verificações» de teste (são 405). Quem confiar no topo destes
   ficheiros parte de premissas falsas. Detalhe completo na secção 1.11.

2. **O canal de aviso automático está morto na prática.** A promessa
   central («o radar deixou de precisar de ser aberto») depende do resumo
   diário, e: o e-mail está por configurar (`email.para` vazio, sem
   `email_senha.txt`), a marca `ultimo_resumo` nunca foi gravada (nenhum
   resumo com conteúdo chegou a sair), o `AVISOS.txt` não existe em
   disco, e há **um único filtro com alerta ligado** («CPV IT»), cujos 56
   reconhecimentos são todos `acervo` — zero avisos novos desde que foi
   ligado. O mecanismo está construído e testado; a última milha (um
   destino de e-mail e uma palavra-passe) nunca foi ligada.

3. **30 dos 110 documentos têm um estado de erro obsoleto e irreparável
   pelo caminho normal.** `texto_estado = "erro: cryptography>=3.1 is
   required for AES algorithm"` — a dependência **já está instalada**
   (cryptography 50.0.1, no Python da pasta e no do sistema), mas
   `extrair_textos()` só processa documentos com `texto_estado IS NULL`,
   por isso estes nunca serão retentados. Do mesmo género: 12 das 18
   linhas de `analise` têm `modelo` no formato antigo (`openai/gpt-oss-120b`
   sem prefixo de fornecedor), que nenhuma migração converte.

4. **Tudo vive num único PC, dentro do OneDrive, sem cópia externa.**
   As cópias diárias (`copias/`, 3 ficheiros até hoje) estão no mesmo
   disco e na mesma pasta sincronizada que já é apontada no próprio
   `ESTADO.md` como capaz de bloquear a base a meio de uma escrita. O
   repositório git tem 67 commits e **nenhum remoto**. Um disco morto ou
   uma conta OneDrive com problemas leva código, histórico, triagem e
   cópias ao mesmo tempo. A triagem é o único dado declaradamente
   irrecuperável.

5. **O servidor é o de desenvolvimento do Flask, sem autenticação nem
   CSRF, com consultas de 7 s ao alcance de um clique.** O
   `/contratos/resumo` sem filtro custa ~7 s (medido a 30/08 no corpus de
   7 anos); as rotas POST que mudam estado (`/verificar`, `/estado/...`,
   `/filtros/.../apagar`) aceitam qualquer pedido vindo do browser — uma
   página maliciosa aberta noutro separador pode fazer POST a
   `localhost:8765`. Em uso local e pessoal o risco é baixo, mas está
   identificado no próprio `ESTADO.md` como pré-requisito de partilha e
   convém não o esquecer: hoje **não há nenhuma** barreira.

### Registo de risco (ver secção 5 para os cenários)

| # | Item | Severidade | Probabilidade |
|---|------|-----------|---------------|
| R1 | Token das capturas `curl_*.txt` expira → recolha pára | Alta | Certa (recorrente; aviso a vermelho existe, recuperação manual ~2 min) |
| R2 | Perda do PC/disco → código, base, triagem e cópias perdidos de uma vez | Crítica | Baixa |
| R3 | OneDrive bloqueia/trunca `radar.db` durante escrita | Alta | Média (documentado como já observado em erros de lock) |
| R4 | Vortal muda a API pública (3 saltos) → ~42 % das peças param | Média | Média |
| R5 | acingov muda o ZIP directo / JSF muda `acessoDocs.jsp` → ~48 %/~9 % das peças param | Média | Média |
| R6 | Groq encerra/reduz o free tier → leitura de peças pára (reservas medidas como insuficientes) | Média | Média |
| R7 | DR muda o formato das secções numeradas → `campos_do_detalhe()` degrada em silêncio parcial | Alta | Baixa–média |
| R8 | DR muda os `screenservices`/OutSystems → recolha inteira pára | Crítica | Baixa |
| R9 | dados.gov muda a API ou o identificador do conjunto → corpus deixa de actualizar | Média | Baixa |
| R10 | Modelo devolve JSON fora do contrato → campos por preencher (parcialmente mitigado: cercas markdown tratadas, `juntar_leituras` preserva o que havia) | Baixa | Média |
| R11 | Volume duplica (anúncios 130 k / contratos 2,7 M) → `/contratos/resumo` ~14 s, importação e migrações a dobrar | Média | Alta (é o crescimento natural) |
| R12 | Verificação dupla em simultâneo (relógio + botão + tarefa) → pedidos a dobrar ao DR | Baixa | Média (tolerada por `INSERT OR IGNORE`; sem trinco entre `relogio()` e `comecar_verificacao()`) |
| R13 | Tarefas do Windows apagadas/perdidas → radar só recolhe com painel aberto | Alta | Baixa (aviso a vermelho no painel, com cache de 60 s) |
| R14 | CSRF/porta local aberta a POST de qualquer página no browser | Baixa | Baixa |
| R15 | Duas instâncias na porta 8765 (SO_REUSEADDR) → código velho a responder | Média | Baixa (documentado, com diagnóstico escrito) |

---

## 1. Inventário funcional

Formato de cada entrada: **o que faz · como se aciona · entradas/saídas ·
erros tratados / não tratados · fluxo · estado · ligação ao painel**.

### 1.1 Recolha de anúncios (DR, parte L)

- **O que faz:** pagina a pesquisa do portal do DR com termo vazio e
  janela de `dias_catchup` (15) dias, e guarda cada anúncio novo
  (`ref`, título, entidade, data, tipo, url) sem qualquer filtro à
  entrada. `recolher()` → `guardar()` (radar.py:609, 2439).
- **Acionada por:** tarefas do Windows 09:00/17:00 (`verificar.bat` →
  `--uma-vez`); `relogio()` (thread do painel, recupera slots falhados);
  botão «Verificar agora» (POST `/verificar` → thread);
  `--historico N` (janela alargada, uma vez).
- **Entradas:** `curl_DR.txt` (cabeçalhos, token, corpo do pedido),
  `config.json`. **Saídas:** linhas em `anuncios`, amostra em
  `amostras/ultima_colheita.json`, marcas `ultima_*` em `estado`.
- **Erros tratados:** falta da captura; corpo ilegível; resposta sem
  JSON (guarda `amostras/resposta_inesperada.txt` e avisa que o token
  pode ter expirado); falha de rede (mensagem própria); portal a recusar
  pesquisa vazia (cai para `termos_de_reserva`); sucesso decidido por
  booleano e não por substring (correcção histórica documentada).
  **Não tratados:** nenhum *retry* de página falhada a meio (o `break`
  abandona o termo); duas recolhas simultâneas não se excluem entre o
  `relogio()` e o botão (toleradas por `INSERT OR IGNORE`, mas os
  pedidos ao portal duplicam).
- **Fluxo:** captação → funil de triagem. **Estado:** activa, verificada
  hoje (slot 30/08 09:01, «ok, 1022 anúncios lidos»). **Painel:** barra
  lateral (ponto verde/vermelho, mensagem), botão no topo de Anúncios/
  Quadro/Calendário.

### 1.2 Leitura do detalhe (CPV, prazo, preço, NIF, texto integral)

- **O que faz:** um POST por anúncio ao serviço de detalhe; guarda o
  texto integral em `anuncios.texto` e extrai por parsing de secções
  numeradas (`seccoes_do_texto`, `campos_do_detalhe`) o CPV, prazo,
  preço base, plataforma, link das peças e NIPC. `ler_detalhes()` trata
  40/verificação dentro da janela `detalhe_dias` (60);
  `ler_detalhe_de()` lê um anúncio na hora ao abrir a ficha;
  `reparsear()` (`--reler`) recalcula tudo do texto guardado, sem rede.
- **Erros tratados:** captura em falta/ilegível; resposta sem JSON
  (aborta a volta com aviso de captura expirada); falha de rede (pára a
  volta). **Não tratados:** um anúncio individual cujo texto venha vazio
  fica `detalhe_lido=1` com campos vazios, sem marca distintiva; não há
  reprocesso automático dos 60 588 anúncios históricos sem detalhe
  (por decisão: são arquivo).
- **Estado:** activa. 5 493 lidos / 66 081 (8,3 %); 5 455 com NIF.
- **Painel:** transparente (a ficha lê na hora; a lista mostra
  «ainda sem detalhe lido»).

### 1.3 Vigilância de alterações (B05) e rectificações

- **O que faz:** `reler_marcados()` relê por verificação até 25 anúncios
  interessa/quadro com prazo aberto; `_guardar_detalhe()` compara prazo
  e preço base (só valor→valor, `diferencas_do_detalhe`) e grava na fila
  `alteracoes` + histórico da ficha. `ligar_retificacoes()` liga títulos
  «Retificação ao Anúncio n.º X» ao original, idempotente pelo
  histórico.
- **Erros tratados:** campo que passa a vazio não avisa (parser a
  tropeçar ≠ alteração); falha de rede pára a volta sem estragar nada.
  **Não tratados:** anulações (sem formato no DR — decisão registada).
- **Estado:** activa mas **ainda sem disparo real** — a tabela
  `alteracoes` tem 0 linhas (há só 3 anúncios «interessa»; foi ensaiada
  sobre cópia com prorrogação simulada). **Painel:** histórico da ficha
  + secção «Alterados» do resumo.

### 1.4 Peças do procedimento (documentos)

- **O que faz:** `obter_documentos()` traz o PDF oficial do anúncio
  (100 % dos casos) e as peças da plataforma: acingov (ZIP directo),
  vortal (3 saltos de API pública), aplicação JSF
  (anogov/ComprasPT/ESPAP, reconhecida pela assinatura
  `/faces/app/acessodocs.jsp`, com `decryptservlet` no mesmo servidor).
  Ficheiros para `documentos/<ref>/`, índice na tabela `documentos`.
  Fila com um trabalhador (`pedir_documentos`), accionada ao marcar
  «interessa» ou pelos botões «Trazer/Actualizar peças».
- **Erros tratados:** ficheiro >60 MB (desiste por pedaços, nomeia os
  excluídos, marca `parcial`); plataforma desconhecida (aviso e botão de
  abrir a plataforma); falha total (`docs_estado='falhou'` +
  `docs_ultimo_erro`); excepção na thread cai em estado terminal (nunca
  fica «pendente» para sempre); nomes de ZIP sanitizados
  (`nome_seguro`); páginas JSF só seguem endereços do mesmo servidor.
  **Não tratados:** não há *retry* automático de um `falhou`; a fila
  perde-se se o processo morrer (os pedidos não são persistentes — o
  anúncio fica `pendente` até alguém carregar de novo... na verdade fica
  `pendente` na base e a ficha recarrega para sempre até novo pedido;
  o estado `pendente` órfão só se resolve com novo clique).
- **Estado:** activa; 19 anúncios com documentos, 110 ficheiros, 46 MB.
- **Painel:** caixa «Peças do procedimento» na ficha, com estados.

### 1.5 Extracção de texto das peças

- **O que faz:** `extrair_textos()` tira o texto dos PDFs (pypdf), com
  marca `\f` em linha própria entre páginas (B12); abre ZIPs que são
  peças (`texto_do_zip`); distingue `ok` / `scan` (digitalização) /
  `erro: ...` / `não é PDF`. `e_pdf()` decide pelos bytes, rejeitando
  ZIPs com PDF por comprimir.
- **Erros tratados:** PDFs cifrados (erro registado), digitalizações
  (`scan`, candidatas a OCR futuro), ZIP estragado. **Não tratados:**
  **estados de erro nunca são retentados** — os 30 documentos com
  `erro: cryptography...` de antes da dependência estar instalada ficam
  presos (só `texto_estado IS NULL` entra na fila). Sem OCR.
- **Estado:** activa; 56 `ok`, 30 `erro` obsoleto, 20 `não é PDF`,
  4 `scan`.

### 1.6 Leitura das peças por modelo (LLM)

- **O que faz:** `analisar_pecas()` recorta as zonas relevantes do CE e
  do PC por âncoras tituladas (`_janelas_do_recorte`, tecto 7 000
  caracteres) e faz três pedidos JSON (objecto+localização; equipa;
  documentos da proposta+preço anormalmente baixo), descendo a cadeia
  `FORNECEDORES` (Groq → NVIDIA → OpenRouter) até alguém responder.
  Grava em `analise` com fontes por página («CE.pdf (pág. 2–4)») e
  o modelo que respondeu. Configurável campo a campo no `config.json`
  (`leituras`, B08), com validação que nunca desliga uma leitura em
  silêncio. Corre na fila (`pedir_analise`) ou dentro do trabalhador
  das peças, e por `--ler-pecas [tudo]`.
- **Erros tratados:** 429 por minuto (espera o `retry-after`, 3
  tentativas); tecto diário (pára de imediato, `_ESGOTADOS` por
  fornecedor/dia, mensagem só quando a cadeia toda esgota); leitura
  parcial preserva campos, fontes e modelos anteriores
  (`juntar_leituras`/`juntar_fontes`); JSON dentro de cercas markdown;
  texto por extrair na hora sem rede; scans identificados. **Não
  tratados:** *timeout* por fornecedor (o NVIDIA a 240 s consome o
  timeout global — anotado no ESTADO como decisão consciente);
  sem validação semântica da resposta (é para isso que existe o
  `ensaio-de-leitura`).
- **Estado:** activa; 18 análises gravadas. **Nota de divergência:** o
  `ESTADO.md` diz que «a cadeia nunca correu pelo caminho normal do
  radar», mas `analise.modelo` contém `groq:...*, nvidia:...` e
  `nvidia:..., openai/gpt-oss-120b` **na base de trabalho** — a cadeia
  já desceu até ao NVIDIA em produção pelo menos duas vezes. O ponto 2
  da lista «o que falta verificar» do ESTADO está de facto cumprido e
  não foi actualizado.
- **Painel:** tabela «Essencial» da ficha, com «lido e não consta»
  distinto de «ainda não lido» (`foi_lido`).

### 1.7 Corpus de contratos (Portal BASE / IMPIC)

- **O que faz:** `importar_contratos()` resolve o endereço semanal pela
  API do dados.gov, descarrega `contratos<ano>.zip`, lê o JSON objecto a
  objecto e enche `contratos.db` (ficheiro próprio, fora do git):
  contratos, adjudicatários e CPV em tabelas filhas com índices únicos
  anti-duplicação, desescape de HTML à entrada, chave de entidade
  (NIF ou `n:`+nome), nome canónico (`resolver_entidades`),
  `fim_estimado` calculado. Reimportar substitui o ano.
- **Acionada por:** tarefa semanal de segunda 08:00 (`contratos.bat`),
  botão «Actualizar contratos» (thread com trinco `_ACTUALIZAR` +
  estado em `corpus_estado`), `--contratos [anos]`.
- **Erros tratados:** anos sem dados (avisa e segue); painel fechado a
  meio (trinco é a verdade, marca «interrompida» explicada); duplicados
  entre anos (índices únicos); prazos absurdos (fim vazio); NIF em
  falta (chave `n:`, marcada «sem NIF» no ecrã). **Não tratados:**
  falha de rede a meio de um ano deixa o ano apagado até à próxima
  passagem? Não — o DELETE e os INSERT correm na mesma transacção
  (`with liga_corpus()`), portanto um rebentamento faz rollback; mas a
  descarga de 91–268 MB é um único `requests.get` em memória, sem
  retoma.
- **Estado:** activa; 1 363 300 contratos 2020–2026, 1,65 GB, última
  importação 28/08 03:15.
- **Painel:** separadores Contratos e Renovações, ficha de entidade,
  blocos da ficha do anúncio, indicadores.

### 1.8 Painel — vistas

| Vista | Rota | O que mostra | Estado |
|---|---|---|---|
| Anúncios | `/` | lista em cartões, 20/página, abas por estado com contagens dentro do filtro, filtros (q, exclusões, entidade, CPV+árvore, op E/OU, plataforma, prazo, datas), filtros guardados, exportação CSV | activa |
| Alertas | `/alertas` | gestão de filtros/alertas (taxa de acerto B06), entidades seguidas, criação de filtro com árvore, config. do e-mail, janela do urgente (B13), histórico de avisos | activa |
| Contratos | `/contratos` | pergunta-primeiro; tabela com fim estimado; 7 gráficos sob procura (`/contratos/resumo`); barra do corpus com botão de actualizar; CSV com tecto 50 000 | activa |
| Renovações | `/renovacoes` | contratos pelo fim estimado, janela 3/6/12/24 meses (whitelist), pergunta-primeiro | activa |
| Quadro | `/quadro` | kanban de «interessa»: fases editáveis, arrastar (fetch JSON), etiquetas, soma de preços base por coluna (B11) | activa |
| Calendário | `/calendario` | grade de 45 dias, pílula por prazo com a fase, fins-de-semana sombreados | activa |
| Indicadores | `/indicadores` | KPI, funil 30 dias, fases, saúde (capturas, plataformas, base, corpus), ligações que abrem exactamente a lista que confirma o número | activa |
| Ficha do anúncio | `/anuncio/<ref>` | essencial (12 campos) / anúncio completo (28 secções), peças, prazo, responsável, histórico, homólogos (B02), histórico de adjudicações + referência de preço + desconto (B04) | activa |
| Ficha de entidade | `/entidade/<chave>` | os dois papéis (compra/ganha), KPI, gráficos, filtro próprio com períodos rápidos, seguir (B10) | activa |

- **Erros tratados no painel:** datas de filtro inválidas avisadas
  (`avisos_de_datas`); página fora do intervalo devolve a última;
  filtros parciais nunca aplicados em silêncio (`filtro_para` + nota);
  404 do anúncio com página completa; lixo em `min`/`pag` ignorado.
- **Não tratados:** sem autenticação, sem CSRF; `ref` vindo do DR é
  interpolado em atributos HTML sem escape em alguns pontos
  (`cartao()`, `accao()` com ref no destino) — dados externos tratados
  como confiáveis (risco baixo: o formato observado é `NNNNN/AAAA`).

### 1.9 Alertas, resumo diário e seguidas

- **O que faz:** um alerta é um filtro guardado com `alerta=1`.
  `registar_alertas()` reconhece (depois de `ler_detalhes()`, com a
  mesma `condicoes()` da lista, só a parte aplicável a anúncios);
  `enviar_resumo()` envia uma vez por dia a partir da `hora_resumo`
  (e-mail se configurado; escreve sempre `AVISOS.txt`; sem canal, o
  ficheiro é a entrega e o estado avança). Seguidas (B10) e alterações
  (B05) entram em secções próprias. Acervo marcado ao ligar.
- **Erros tratados:** e-mail por configurar vs. falha a sério
  (só a segunda deixa por enviar, para repetir); autenticação SMTP
  recusada com mensagem específica de palavra-passe de aplicação.
  **Não tratados:** nada verifica que a `hora_resumo` é alcançável
  pelas verificações agendadas (com verificações às 09:00/17:00 e
  `hora_resumo` 17:00, o resumo depende do minuto em que a segunda
  corre — hoje corre 17:01–17:09, funciona por acaso da ordem).
- **Estado:** construído e testado; **nunca produziu uma entrega**
  (ver problema urgente n.º 2).

### 1.10 Funções de manutenção e CLI

| Comando | Função | Estado |
|---|---|---|
| `--uma-vez` | `verificar()` + regista slot | activa (é o que as tarefas correm) |
| `--historico N` | recolha alargada única | usada (2 anos importados a 28/08) |
| `--reler` | `reparsear()` sem rede | usada (encheu `nif`, ComprasPT) |
| `--ler-pecas [tudo]` | fila de leitura pelo modelo | usada |
| `--importar-cpv F` | carrega `cpv_dict` | usada uma vez (9 454 códigos) |
| `--contratos [anos]` | corpus BASE | activa (semanal) |
| `--descartar-expirados` | arruma «por ver» com prazo passado | usada (0 por ver expirados hoje; 4 097 descartados) |
| cópia de segurança | `copia_de_seguranca()`, VACUUM INTO diário, 7 guardadas | activa desde 28/08 (3 cópias) |

### 1.11 Divergências documentação ↔ código/base (explícitas)

| Onde | O que diz | O que é | Gravidade |
|---|---|---|---|
| `ESTADO.md` «Como está a correr» | ~5 100 anúncios, todos com detalhe lido, 60 dias; base limpa aos 60 dias por decisão | 66 081 anúncios (28/08/2024–28/08/2026), 5 493 com detalhe (8,3 %). A secção «Dois anos de anúncios» do próprio ESTADO contradiz o topo — são camadas de datas diferentes sem a de cima ter sido corrigida | **Alta** — é o parágrafo de orientação inicial |
| `ESTADO.md` «O que falta verificar na cadeia» | «a cadeia nunca correu pelo caminho normal» | `analise.modelo` na base de trabalho tem 2 linhas com `nvidia:` — correu e desceu | Média |
| `ESTADO.md` «Coisas a saber antes de mexer» | «o painel limita a tabela a 500 linhas» | paginação a 20/página desde a mudança documentada noutra secção | Baixa |
| `LEIA-ME.md` §14 | «O radar lê o anúncio, não as peças do procedimento» e «enquanto o IMPIC não der acesso à API, essa parte fica de fora» | as peças são trazidas e lidas por modelo; o corpus vem do dump do IMPIC desde há dias | **Alta** — é o manual do utilizador |
| `LEIA-ME.md` §12 | «82 verificações» | 405 testes | Baixa |
| `LEIA-ME.md` §5 | não menciona exclusões, op E/OU, prazo, renovações, alertas | existem todos | Média |
| `CLAUDE.md` | «~8200 linhas» | 9 938 linhas | Baixa |
| `CLAUDE.md`/hooks | «são 118 testes» (comentário no hook `testes_antes_do_commit.py`) | 405 | Baixa |
| Tabela `estado` | chaves `ultimo_aviso`, `ultimo_aviso_texto` | não existem no código actual (esquema de avisos antigo); lixo inofensivo | Baixa |
| `contratos.db` | índices `ix_adj_c`, `ix_cpv_c` presentes | não são criados por `iniciar_corpus()` — legado; num corpus refeito de raiz desaparecem (sem impacto: `ux_adj`/`ux_cpv` cobrem os mesmos acessos por `contrato_id`) | Baixa |

---

## 2. Inventário técnico

### 2.1 Ficheiros

| Ficheiro | Linhas | Papel |
|---|---|---|
| `radar.py` | 9 938 | tudo: recolha, parsing, documentos, LLM, corpus, painel, agendamento (259 funções de topo) |
| `teste_radar.py` | 3 230 | 405 testes de regressão em 98 classes, 0,26 s, sem rede/base |
| `.claude/hooks/proteger_dados.py` | 125 | PreToolUse: recusa escritas em `curl_*.txt`/`radar.db*` (por `file_path` e por texto de comando; SQL de escrita sem base apontada) |
| `.claude/hooks/testes_antes_do_commit.py` | 72 | PreToolUse: trava `git commit` com testes a falhar; usa o Python da pasta |
| `.claude/hooks/verificar_sintaxe.py` | 65 | PostToolUse: `py_compile -W error::SyntaxWarning` do que foi escrito, incluindo por comando |
| `.claude/hooks/teste_hooks.py` | 104 | testes dos hooks |
| `.claude/skills/estado-radar/` | 31+106 | estado da base em só-leitura, sem importar `radar.py` |
| `.claude/skills/ensaio-de-leitura/` | 65+234 | confronto linha-a-linha da resposta do modelo com o documento; sem `--sem-modelo` relê sobre **cópia** |
| `.claude/agents/explorador-de-plataforma.md` | 65 | subagente de investigação de plataformas novas, só leitura |
| `.bat` ×10 | ~150 | atalhos do utilizador (`_python.bat` escolhe o Python da pasta) |
| `config.json` | 39 | configuração viva (ver 2.5) |
| `curl_DR.txt` / `curl_detalhe.txt` | 166 KB / 5,7 KB | capturas DevTools de 23/08 (7 dias); token ainda válido (recolha ok hoje) |
| `requirements.txt` | 4 deps | flask, requests, pypdf, cryptography |
| `radar.db` | 92 MB | base de trabalho (ver 2.6) |
| `contratos.db` | 1 648 MB | corpus (fora do git) |
| `documentos/` | 46 MB, 19 pastas | peças em disco |
| `copias/` | 208 MB, 3 cópias | VACUUM INTO diário |
| `amostras/` | 2 ficheiros | última colheita + detalhe bruto de exemplo |
| `python/` + `libs/` | ~36 MB | Python 3.14 embutido + pacotes (modo pen) |
| `painel.log` | 4 KB | **obsoleto** — access log do Flask de 27/08, nada escreve nele desde então |
| `concorrentes/` | 12 .md | prova da análise competitiva, com data |

### 2.2 Rotas (35, todas sem autenticação; POST para tudo o que escreve)

| Método | Rota | Propósito | Função |
|---|---|---|---|
| GET | `/` | lista de anúncios (filtros+paginação) | `painel` (radar.py:5316) |
| GET | `/cpv.json?de=` | vocabulário CPV com contagens por fonte, com cache | `cpv_json` (6113) |
| GET | `/csv` | exportação de anúncios do filtro | `exportar` (6231) |
| GET | `/alertas` | gestão de filtros/alertas/e-mail | `alertas` (6427) |
| GET | `/contratos` | lista de contratos (pergunta-primeiro) | `contratos` (7670) |
| GET | `/contratos/resumo` | os 7 gráficos em HTML, sob o filtro | `contratos_resumo` (7235) |
| GET | `/contratos/csv` | exportação de contratos (exige filtro; tecto 50 000) | `contratos_csv` (7567) |
| GET | `/renovacoes` | contratos pelo fim estimado | `renovacoes` (7921) |
| GET | `/entidade/<chave>` | ficha da entidade (dois papéis) | `entidade` (7384) |
| GET | `/anuncio/<ref>` | ficha do anúncio (lê detalhe na hora se faltar) | `ficha` (8760) |
| GET | `/documento/<ref>/<nome>` | serve peça do disco (caminho confinado à pasta) | `servir_documento` (9089) |
| GET | `/quadro` | kanban | `quadro` (9225) |
| GET | `/calendario` | grade de prazos | `calendario` (9303) |
| GET | `/indicadores` | métricas da própria base | `indicadores` (9465) |
| POST | `/verificar` | arranca verificação em thread com trinco | `verificar_agora` (6144) |
| POST | `/estado/<ref>/<novo>` | triagem (interessa/descartado/novo); interessa → fila de peças | `mudar_estado` (6158) |
| POST | `/sou` | identidade em cookie de 1 ano | `definir_quem` (6186) |
| POST | `/responsavel/<ref>` | atribuição | `definir_responsavel` (6197) |
| POST | `/filtros/guardar` | guarda/actualiza filtro pelo nome | `filtro_guardar` (6051) |
| POST | `/filtros/<id>/apagar` | apaga filtro + reconhecimentos | `filtro_apagar` (6063) |
| POST | `/alertas/criar` | cria filtro do formulário (recusa preserva campos) | `alerta_criar` (6627) |
| POST | `/alertas/email` | destino + hora do resumo | `alertas_email` (6662) |
| POST | `/alertas/<id>/trocar` | liga/desliga alerta (acervo ao ligar) | `alerta_trocar` (6674) |
| POST | `/alertas/enviar` | resumo já (forçado) | `alertas_enviar` (6692) |
| POST | `/alertas/urgente` | janela do urgente 1–90 | `alertas_urgente` (6408) |
| POST | `/entidade/<chave>/seguir` | segue/deixa de seguir | `entidade_seguir` (7524) |
| POST | `/contratos/actualizar` | actualização do corpus em thread | `contratos_actualizar` (7618) |
| POST | `/documentos/<ref>` | põe peças na fila | `trazer_documentos` (9055) |
| POST | `/analisar/<ref>` | põe leitura na fila | `analisar` (9076) |
| POST | `/quadro/mover` | move cartão (JSON; valida fase e anúncio) | `quadro_mover` (9720) |
| POST | `/quadro/fase/nova`, `/<id>/renomear`, `/<id>/apagar` | gestão de fases (apagar exige >1; cartões migram) | (9745–9775) |
| POST | `/quadro/etiqueta/<ref>/nova`, `.../tirar/<id>` | etiquetas globais, cor por rotação | (9778–9802) |

### 2.3 Trabalho em fundo e agendamento

| Job | Mecanismo | Frequência | Como falha |
|---|---|---|---|
| Verificação 09h/17h | tarefas do Windows → `--uma-vez` (processo próprio) | 2×/dia | se as tarefas faltarem, painel avisa a vermelho (`tarefas_em_falta`, cache 60 s); os erros da própria verificação vão para `ultima_mensagem`/`ultima_ok` |
| Corpus semanal | tarefa Windows segunda 08:00 → `--contratos` | 1×/semana | sem retoma de descarga; falha visível nos indicadores («última importação há N dias», amarelo >14) |
| `relogio()` | thread daemon no painel; recupera slots falhados | por minuto | erro gravado em `ultimo_erro_relogio` (não visto em lado nenhum do painel — só por SQL) |
| Verificação por botão | thread com trinco `_VERIFICACAO` | a pedido | excepção marca `ultima_ok=0` com mensagem; **sem exclusão mútua com o `relogio()` nem com a tarefa** (duplicação tolerada, pedidos a dobrar) |
| Fila de peças | `queue.Queue` + 1 trabalhador daemon | a pedido | excepção → `docs_estado='falhou'` + `docs_ultimo_erro`; fila não persistente (morre com o processo) |
| Fila de análise | idem (`_FILA_ANALISE`) | a pedido | `analise_ultimo_erro`; idem persistência |
| Actualização do corpus | thread + `Lock` + estado na base | a pedido | estado terminal garantido; painel distingue «interrompida» |
| Cópia de segurança | dentro de `verificar()`, 1×/dia | diária | falha só faz `print` (invisível no painel) |
| Resumo diário | dentro de `verificar()` ≥ `hora_resumo` | 1×/dia | estado em `ultimo_resumo_estado` |

### 2.4 Chamadas externas

| Serviço | Propósito | Erros | Limites/custo |
|---|---|---|---|
| DR `DataActionGetPesquisas` (POST) | pesquisa paginada | content-type, rede, token expirado (aviso) | 1 s de pausa/página; token de sessão expira |
| DR `DataActionGetAllConteudoDetalheData` (POST) | detalhe por anúncio | idem | 1 s/anúncio; 40/verificação |
| DR `URL_PDF` (GET) | PDF oficial do anúncio | ignora falha em silêncio (peças seguem) | — |
| acingov (GET ZIP) | peças | ZIP inválido, tecto 60 MB×4 | — |
| Vortal API pública (3 GET) | peças | `.json()` pode rebentar → apanhado no `obter_documentos` | nome do parâmetro `contractNoticeUId` é frágil (400 com o nome «óbvio») |
| JSF `acessoDocs.jsp` + `decryptservlet` (GET) | peças | página sem docs = lista vazia (indistinguível de código truncado — armadilha documentada) | encoding forçado windows-1252 |
| dados.gov API + zip do IMPIC (GET) | corpus | `raise_for_status`; sem retoma | dump semanal; 91–268 MB/ano em memória |
| Groq `/chat/completions` | leitura de peças | 429/min (espera), 429/dia (pára), formato | **8 000 tokens/min, 200 000/dia**; ~6 000 tokens/concurso ⇒ ~30 concursos/dia; custo 0 € |
| NVIDIA `integrate.api.nvidia.com` | reserva (mesmo modelo) | fila silenciosa em rajada (ReadTimeout 240 s) | free tier; `reasoning_effort=low` |
| OpenRouter | reserva (modelo grátis) | 429 sistemático em recortes reais | pool partilhado — medido como não utilizável |
| SMTP (Gmail por omissão) | resumo diário | auth recusada com mensagem própria | por configurar |
| Google Fonts (browser) | tipografia do painel | fallback `system-ui` sem rede | — |

### 2.5 Configuração

**`config.json` (vivo) vs. `CONFIG_INICIAL`:** `horas_verificacao`
(09:00/17:00 — relógio interno; as tarefas do Windows têm as horas
**duplicadas** no `agendar.bat`, é preciso mudar nos dois sítios),
`dias_catchup` 15, `recuperar_slot_falhado`, `abrir_browser_ao_encontrar`
false, `detalhes_por_volta` 40, `relidos_por_volta` 25, `dias_urgente` 10
(editável em `/alertas`), `copia_de_seguranca`/`copias_a_guardar` 7,
`alertas` true, `email` (só `para` e `hora_resumo` editáveis no ecrã; a
conta que envia fica no ficheiro + `email_senha.txt`), `detalhe_dias` 60,
`modelo_pecas`/`modelos_pecas`/`fornecedor_pecas`, `por_pagina` 25 (da
**recolha**, não da lista), `paginas` 5000 (tecto de segurança),
`termos_de_pesquisa` [""] e `termos_de_reserva`. A chave `leituras`
(B08) é aceite mas não está no `CONFIG_INICIAL` — só existe se alguém a
escrever à mão.

**Hardcoded (constantes com nome, deliberadas):** `PORTA` 8765,
`POR_PAGINA` 20 (lista), `TECTO_CSV` 50 000, `TECTO_RECORTE` 7 000,
`MAX_FICHEIRO` 60 MB, `DIAS_CALENDARIO` 45, `MESES_RENOVACOES`
(3,6,12,24), `LIMITES_ESCALAO`/`ESCALOES`, `LIMITES_DESCONTO`,
`MINIMO_PARA_TAXA` 20, `MINIMO_PARA_ESCADA` 8, `MINIMO_PARA_DESCONTO` 5,
`MAX_BARRAS_TEMPO` 16, `TAREFAS_VALIDADE` 60 s, `FORNECEDORES` (URLs e
modelos), `PLATAFORMAS`/`PLATAFORMAS_COM_PECAS`, `ASSINATURA_JSF`,
`CONJUNTO_CONTRATOS`, âncoras e instruções das leituras (com override
por config), `_PALAVRAS_OCAS`. Único valor «hardcoded» questionável: o
`http://localhost:%d` nos links do resumo por e-mail — num telemóvel o
link não abre nada.

**Segredos:** `groq_API_KEY.txt`, `nvidia_API_KEY.txt`,
`openrouter_API_KEY.txt` presentes; `email_senha.txt` ausente;
variáveis de ambiente aceites como alternativa. `.gitignore` largo
(`*api_key*`, `*token*`, `*secret*`, `*.key`) — verificado que cobre os
nomes existentes.

### 2.6 Base de dados

**`radar.db` — 92 MB, WAL, `busy_timeout` 30 s** (contagens de 30/08):

| Tabela | Linhas | Escrita | Colunas principais |
|---|---|---|---|
| `anuncios` | 66 081 | 2×/dia (inserts) + detalhes/releituras (updates) | ref PK, titulo, entidade, data_pub, tipo, url, cpv, prazo, preco_base, plataforma, detalhe_lido, estado, visto_em, fase_id, texto, pdf_url, link_pecas, docs_estado, responsavel, nif, titulo_norm, entidade_norm |
| `documentos` | 110 | ao trazer peças | ref, nome, ficheiro, tamanho, origem, obtido_em, texto, texto_estado |
| `analise` | 18 | ao ler peças | ref PK, objecto, equipa, documentos_proposta, preco_anormalmente_baixo, localizacao, modelo, fontes, quando |
| `historico` | 4 146 | por acção | ref, quem, accao, detalhe, quando |
| `cpv_dict` | 9 454 | uma vez | codigo PK, codigo8, descricao, simples |
| `alertas_vistos` | 56 | por verificação | (filtro_id, ref) PK, visto_em, enviado_em |
| `alteracoes` | 0 | raro | ref, campo, antes, depois, detectado_em, avisado_em |
| `filtros_guardados` | 1 | a pedido | nome UNIQUE, consulta (query string), alerta, quem, criado_em |
| `fases` / `etiquetas` / `anuncio_etiquetas` | 5 / 0 / 0 | a pedido | quadro |
| `pessoas` | 1 | a pedido | nome UNIQUE |
| `entidades_seguidas` / `seguidas_vistos` | 1 / 10 | a pedido/verificação | chave PK / (chave, ref) PK |
| `slots` | 15 | 2×/dia | (dia, hora) PK, corrido_em, novos |
| `estado` | 7 | por verificação | chave/valor (inclui 2 chaves legadas) |

Índices: `data_pub`, `cpv`, `estado`, `titulo_norm`, `entidade_norm`
(anti-desserialização, medidos 4,7 s→0,4 s), `cpv_dict(codigo8)`,
`documentos(ref)`, `historico(ref)`, `alertas_vistos(enviado_em)`,
`alteracoes(avisado_em)`.

**`contratos.db` — 1 648 MB, WAL:**

| Tabela | Linhas | Escrita |
|---|---|---|
| `contratos` | 1 363 300 | semanal (2 anos substituídos, ~400 k linhas) |
| `contrato_adjudicatario` | 1 384 045 | idem |
| `contrato_cpv` | 1 385 196 | idem |
| `entidades` | 137 898 | recalculada no fim de cada importação |
| `entidade_nomes` | 178 475 | idem |
| `corpus_estado` | 4 | marcas |

Por ano: 2020: 176 489 · 2021: 187 371 · 2022: 176 462 · 2023: 192 067 ·
2024: 225 957 · 2025: 246 731 · 2026: 158 223. Índices: 18 (incluindo os
únicos anti-duplicação `ux_cpv`/`ux_adj`, o parcial `ix_ctr_desconto` e
os pares ordenação+id `ix_ctr_data`/`ix_ctr_fim`; 2 índices legados não
recriáveis pelo código actual — ver 1.11).

### 2.7 Ficheiros e I/O

- **Persistentes:** `radar.db(+wal/shm)`, `contratos.db(+wal/shm)`,
  `documentos/<ref-sanitizado>/`, `copias/radar-AAAA-MM-DD.db` (7),
  `config.json`, capturas, chaves, `amostras/` (últimas colheitas e
  respostas inesperadas), `AVISOS.txt` (quando há resumo).
- **Temporários:** `tempfile.TemporaryDirectory()` para abrir PDFs de
  dentro de ZIPs (único uso de temp); `config.json.estragado` como
  salvaguarda de configuração ilegível.
- **Segurança de caminhos:** `nome_seguro()` + verificação
  `os.path.abspath` em `servir_documento` (path traversal testado).
- **Lixo residual:** `painel.log` (morto desde 27/08), `__pycache__/`,
  `.claude/worktrees/` com 4 worktrees de sessões antigas.

### 2.8 Métricas objectivas

| Métrica | Valor |
|---|---|
| Linhas `radar.py` | 9 938 (~455 KB; ~660 de CSS + ~450 de JS embutidos) |
| Funções de topo | 259 |
| Rotas Flask | 35 (14 GET de página/dados, 21 POST) |
| Threads/filas | 5 (relógio, verificação, corpus, fila docs, fila análise) |
| Integrações externas | 12 (3 endpoints DR, 3 famílias de plataformas, dados.gov, 3 LLM, SMTP, Google Fonts) |
| Testes | 405 em 98 classes, 0,26 s, todos verdes a 30/08; 1 uso de `test_client` — cobertura de rotas quase só indirecta |
| Cobertura formal | não medida (sem ferramenta); testes são de regressão sobre funções puras |
| `with liga()` / `with liga_corpus()` | 86 / 23 (ligação por operação, sem pool — correcto para SQLite+WAL) |
| `except Exception` largos | 11 (todos em threads/hooks com registo em `marca()`; 3 `try/except/pass` verdadeiramente silenciosos: `webbrowser.open`, `os.remove` de cópias, marca dentro de handler de erro) |
| `html.escape` | 152 ocorrências |
| Commits git | 67, só locais, sem remoto |

---

## 3. Avaliação de qualidade

### 3.1 Hotspots de complexidade

As funções de rota que montam HTML por concatenação são as maiores e as
mais difíceis de mexer sem partir nada — cada uma mistura consulta SQL,
lógica de apresentação e strings com `%`-formatting:

| Função | Linhas | Nota |
|---|---|---|
| `ficha` (anúncio) | ~292 | a mais densa: leitura na hora, 12 campos essenciais com 4 estados cada, peças com 5 estados, auto-refresh condicional |
| `indicadores` | ~255 | KPI + funil + saúde + corpus, muitos ramos |
| `contratos` | ~241 | pergunta-primeiro, CTE de paginação, faixas, barra do corpus |
| `painel` (lista) | ~222 | 6 contagens por pedido (abas, plataformas, filtro) |
| `alertas` | ~200 | formulário de 13 campos concatenado num só `%` de ~35 argumentos |
| `renovacoes` | ~197 | ~80 % duplicada de `contratos` (ver 3.2) |
| `condicoes` / `condicoes_contratos` | 183 / 152 | os dois motores de filtro, irmãos com lógica paralela |
| `iniciar_db` / `iniciar_corpus` | 164 / 157 | migrações acumuladas por ordem histórica |

O risco não é bug latente (os testes seguram os fragmentos calculáveis)
— é custo de alteração: qualquer mudança visual obriga a editar strings
posicionais longas, e o próprio ESTADO regista duas quedas na armadilha
da precedência do `%`.

### 3.2 Duplicação

- **`contratos()` vs. `renovacoes()`**: o formulário, as faixas de
  CPV/entidade, o CTE de paginação e a tabela são quase decalcados;
  divergem na ordenação, na janela e em duas colunas. Qualquer correcção
  numa tem de ser lembrada na outra (o padrão «defeito corrigido numa
  vista, vivo na vista irmã» é o que a 2.ª vistoria do ESTADO identifica
  como o principal gerador de bugs do projecto).
- **`condicoes()` vs. `condicoes_contratos()`**: deliberadamente irmãs
  (campos diferentes), mas `frag_texto`/`procura`/`exclui` e o bloco
  op=OU estão escritos duas vezes com pequenas variações (norma por
  coluna). Um bug no COALESCE ou no escape corrige-se em dois sítios.
- **Blocos de faixa "cpv-activo"** repetidos em 4 páginas com pequenas
  diferenças; **selectores de procedimento** montados 3 vezes.
- Duplicações conscientes e documentadas (aceitáveis): horas das
  verificações no `config.json` **e** no `agendar.bat`; limites de
  escalões no CASE SQL e nas etiquetas (comentário avisa).

### 3.3 Tratamento de erros e logging

- **Pontos fortes:** threads nunca morrem em silêncio (estado terminal +
  `marca()`); mensagens de erro em português orientadas à acção («refaz
  a captura», «corre agendar.bat»); a distinção 400-JSON vs. 200-casca
  do OutSystems está codificada; `config.json` estragado é salvaguardado.
- **Pontos fracos:** não há log estruturado nenhum — o diagnóstico vive
  espalhado por `estado`/`corpus_estado` (últimas mensagens, uma de cada
  tipo, **sobrescritas**: `analise_ultimo_erro` guarda só o último erro
  de análise; um dia mau apaga a história). `ultimo_erro_relogio` e
  `docs_ultimo_erro` não aparecem em nenhum ecrã — só por SQL. A cópia
  de segurança falhada faz `print` para uma consola que normalmente
  ninguém vê (pythonw). `painel.log` é um resto morto que sugere um
  logging que não existe.

### 3.4 Nomenclatura e consistência

Consistente e com regras escritas (comentários ASCII, UI acentuada;
`ent`/`adj`/`entid`/`vencid` desambiguados com teste; datas ISO na base,
DD/MM à vista; truncagem só por `corta()`; números por
`mil_pt`/`euros*`). Única nota: `por_pagina` no config é da **recolha** e
`POR_PAGINA` no código é da **lista** — nomes iguais para coisas
diferentes, à espera de confusão.

### 3.5 Secrets e caminhos

Sem segredos no código; chaves em ficheiros gitignorados com padrões
largos; e-mail com a palavra-passe deliberadamente fora do ecrã e do
config. Caminhos todos relativos a `BASE_DIR` (portável em pen). Os
links do resumo apontam para `localhost:8765` — inúteis fora do PC.

### 3.6 Riscos de desempenho (~1,36 M contratos)

- Medidos e gordos: `/contratos/resumo` **sem filtro ~7 s** (cinco
  consultas herdadas; o próprio ESTADO anota como melhoria possível);
  primeira migração de `objecto_norm` ~8 min; `fim_estimado` 349 s
  (ambas únicas). Com filtro, tudo entre 20 ms e 1,5 s — aceitável.
- As decisões anti-armadilha estão no sítio e têm comentário e teste:
  `+` no GROUP BY, LEFT JOIN depois do LIMIT, `IN` vs `EXISTS`, `n_adj`
  em coluna, índice parcial do desconto, cache do `cpv.json` por fonte.
- A duplicar o volume: linear na maioria; o resumo sem filtro passa a
  ~14 s **no dev server multi-thread mas com o GIL** — durante esses
  segundos o painel fica pesado. A importação semanal (2 anos, ~800 k
  linhas + `resolver_entidades` sobre o corpus todo) também cresce.
- `radar.db`: 92 MB para 66 k anúncios com texto integral; a crescer
  ~60-100 anúncios/dia (~1,5 MB/dia com texto). Sem limpeza automática
  da janela (deliberado — «a limpeza não é automática»).

### 3.7 Thread-safety (Flask + SQLite + jobs)

- **Bem:** WAL + `busy_timeout` 30 s; uma ligação nova por operação;
  transacções curtas via `with`; filas com um só trabalhador; trincos
  (`_VERIFICACAO_TRINCO`, `_ACTUALIZAR`, `_TRABALHADOR_LOCK`) com a
  lição «o trinco é a verdade, a marca é só para mostrar» aplicada.
- **Buracos conhecidos e toleráveis:** `relogio()` não consulta o trinco
  da verificação por botão nem sabe da tarefa do Windows — três
  caminhos podem recolher em simultâneo (dados protegidos por
  `INSERT OR IGNORE`; custo: pedidos duplicados ao DR).
  `_ESGOTADOS`, `_CPV_CACHE`, `_TAREFAS_VISTAS` são dicts partilhados
  sem lock (na prática seguros sob o GIL para estes padrões).
  A fila de documentos marca `pendente` na base antes de garantir
  trabalhador vivo — se o processo morrer, `pendente` fica órfão até
  novo clique (a ficha recarrega-se de 3 em 3 s enquanto isso).
- **OneDrive** continua a ser a ameaça real ao SQLite, não a
  concorrência interna.

### 3.8 Testes

405 testes, todos correspondentes a bugs reais e comentados — é uma
suite de regressão exemplar no que cobre. O que **não** cobre: rotas
completas (1 uso de `test_client`), o caminho de rede (por desenho), a
concorrência, e o HTML gerado (um `%s` trocado numa rota só se vê ao
abrir a página). Não há medição de cobertura; a estimativa honesta é
alta nas funções de cálculo/parsing e baixa nas rotas.

### 3.9 Gambiarras e código incompleto, sem rodeios

- O painel inteiro é HTML por concatenação de strings com
  `%`-formatting — funciona, está testado nos fragmentos, mas é a maior
  fonte de custo de manutenção do projecto e já mordeu duas vezes
  (precedência do `%`). Não é dívida escondida: é dívida assumida e
  documentada, mas é dívida.
- `campos_do_detalhe()` faz fallback de plataforma com
  `if "acin" in alvo` — heurística solta fora da lista `PLATAFORMAS`.
- `radar_chave()` (8213) duplica `simplifica().strip()` com outro nome.
- A chave `leituras` do config não tem exemplo no `CONFIG_INICIAL` nem
  no LEIA-ME — funcionalidade B08 invisível para quem não ler o código.
- `essencial_do_anuncio` devolve tuplos posicionais de 4 elementos que a
  `ficha()` desconstrói — qualquer campo novo obriga a mexer nos dois
  em sincronia (já causou o incidente do `sqlite3.Row` rebentado,
  tratado com try/except).
- Estados de erro em `documentos.texto_estado` são terminais para
  sempre (ver problema urgente n.º 3) — falta um caminho de retentativa
  que não seja apagar a linha à mão por SQL.

---

## 4. Fricção de uso diário

### Fluxo A — triagem da manhã (o uso principal)

1. Recolha das 09:00 — **automática** (tarefa Windows).
2. Abrir o painel (`iniciar.bat` ou já aberto) — **manual**, um clique.
3. Ver «Por ver» — **automático**: mais recentes primeiro; mas a aba diz
   61 981, porque os dois anos de histórico sem detalhe vivem no mesmo
   balde da triagem do dia. A triagem real faz-se pela ordenação por
   data ou pelo filtro `prazo=aberto` — funciona, mas o número da aba é
   permanentemente assustador e não distingue «de hoje» de «arquivo».
   *(O `--descartar-expirados` limpou os expirados com prazo lido; os
   ~60 588 sem detalhe não têm prazo para julgar.)*
4. Marcar interessa/descartar — **um clique cada**, posição de scroll
   preservada, peças vêm sozinhas ao marcar interessa.
5. Ler o essencial na ficha — **automático** ao fim de segundos
   (peças + modelo), com a ressalva do orçamento diário da Groq.
   **Onde sai da aplicação:** anexos >60 MB (botão para a plataforma) e
   plataformas sem obtentor (~0,6 %).

### Fluxo B — receber avisos sem abrir o radar

1. Criar filtro e ligar o alerta — **feito no painel**, um só motor.
2. Receber o resumo — **parte-se aqui**: sem `email.para` e sem
   `email_senha.txt`, a entrega é o `AVISOS.txt`… que é um ficheiro na
   pasta que ninguém abre por acaso. Hoje: 1 alerta ligado, 0 avisos
   novos alguma vez produzidos, 0 e-mails. O fluxo existe de ponta a
   ponta no código e **nunca correu com conteúdo**. Semi-manual até a
   conta de envio ser configurada (2 ficheiros + 1 formulário).

### Fluxo C — investigar um concurso a fundo

Ficha → essencial → homólogos (quem ganhou as edições anteriores, com
preço) → histórico da entidade no CPV + régua de preço + desconto →
ficha da entidade → contratos filtrados. **Tudo dentro da aplicação, a
cliques** — este fluxo é o mais bem servido de todos. Sai da aplicação
só para: ler o PDF em si (abre no browser, sem pesquisa integrada —
decisão registada no BACKLOG) e para plataformas com sessão.

### Fluxo D — exportar dados de um período

Anúncios: filtro + «exportar as N linhas (CSV)» — **automático**, com
número anunciado, vírgula decimal, data no nome. Contratos: igual, mas
**exige filtro** e corta a 50 000 linhas (dito no ecrã). Excel português
abre direito. Fricção residual: não há exportação do corpus inteiro
(deliberado) nem formato .xlsx (registado em «Não fazer»).

### Fluxo E — quando o token expira

Painel avisa a vermelho → DevTools → Copy as cURL (bash) → gravar dois
`.txt` → próxima verificação já usa. **Totalmente manual**, ~2 min,
instruções na secção 3 do LEIA-ME. É o único ritual recorrente
obrigatório do sistema e não tem alternativa sem API do DR. As capturas
actuais têm 7 dias e ainda funcionam; a frequência real de expiração não
está registada em lado nenhum (valeria a pena anotar as datas para se
saber o ciclo).

---

## 5. Mapa de fragilidade

### O que quebra se…

- **…a sessão de scraping expirar (R1):** `recolher()` e
  `ler_detalhes()` devolvem «sem JSON, token expirado»; painel a
  vermelho; peças e corpus **não** são afectados (caminhos sem token).
  Recuperação manual de 2 min. Detecção: boa. Ponto cego: se ninguém
  abrir o painel nem ler e-mail (que não há), a paragem só se nota
  quando se procura um anúncio que falta.
- **…uma plataforma mudar o layout (R4/R5):** cada obtentor é
  independente; a falha degrada para `docs_estado='falhou'` com o botão
  manual como alternativa — sem efeito nos anúncios. A Vortal é a mais
  frágil (endpoint descoberto por engenharia inversa do bundle JS, nome
  de parâmetro não-óbvio); a JSF é a mais robusta (assinatura, não
  domínio). Sem monitorização agregada: uma plataforma partida nota-se
  ficha a ficha.
- **…o modelo mudar de resposta (R6/R10):** `response_format` +
  desembrulho de cercas + `juntar_leituras` tornam a degradação parcial
  e não destrutiva; o pior caso realista é «campos por preencher com
  aviso». A troca de modelo/fornecedor é configuração. O risco material
  é comercial (fim do free tier), não técnico.
- **…o schema da BD mudar:** migrações idempotentes nos dois
  `iniciar_*()`; colunas novas são `ALTER TABLE` guardado por
  `PRAGMA table_info`; reparações únicas por marca. O histórico mostra
  o processo a funcionar (norm, chaves, desescape, fim_estimado). Risco
  real: as migrações do corpus correm no arranque do **painel** — um
  corpus antigo aberto pela primeira vez custa minutos sem barra de
  progresso.
- **…o volume duplicar (R11):** ver 3.6. Nada parte; o resumo sem
  filtro e a importação ficam desconfortáveis; `radar.db` segue
  tranquilo.
- **…o DR mudar o formato do texto (R7):** `campos_do_detalhe` passa a
  extrair vazios; como campo vazio não gera aviso de alteração (regra
  anti-lobo), a degradação é **silenciosa** — os anúncios novos ficam
  sem CPV/prazo e só se nota nos filtros. O `--reler` corrige
  retroactivamente depois de arranjar o parser (o texto integral está
  guardado — é a melhor defesa que o projecto tem).

### Pontos únicos de falha

1. **O PC do Afonso** — hardware, OneDrive, sem remoto git, cópias no
   mesmo disco (R2/R3). É o SPOF dominante; tudo o resto degrada, isto
   destrói.
2. **As capturas cURL** — único caminho para o DR; sem elas, sem
   anúncios (R1/R8).
3. **A conta Groq** — as reservas estão medidas como incapazes de
   aguentar carga real; sem Groq, a leitura de peças fica ao ritmo do
   NVIDIA em uso ligeiro ou pára (R6).
4. **O dump do IMPIC** — única fonte do corpus; a alternativa OCDS está
   morta desde 2022 (R9).
5. **O processo único do painel** — filas em memória; morre o processo,
   morrem os pedidos pendentes (mitigado: nada se perde de permanente).

---

## 6. Requisitos retroactivos

### 6.1 Requisitos funcionais

**Recolha e detalhe**

- **FR-01** O sistema recolhe todos os anúncios da parte L da série II
  do DR numa janela de `dias_catchup` dias, sem filtragem à entrada,
  duas vezes por dia. — `recolher()`, `verificar()`, `agendar.bat`
- **FR-02** A deduplicação é pela referência do anúncio (`ref` PK) com
  `INSERT OR IGNORE`. — `guardar()`
- **FR-03** Se o portal recusar pesquisa vazia, o sistema varre por
  termos de reserva configuráveis. — `recolher()`
- **FR-04** O sistema lê o detalhe (texto integral, CPV, prazo, preço
  base, plataforma, link das peças, NIPC) dos anúncios publicados na
  janela `detalhe_dias`, até `detalhes_por_volta` por verificação, e de
  qualquer anúncio no momento em que a ficha é aberta. —
  `ler_detalhes()`, `ler_detalhe_de()`, `campos_do_detalhe()`
- **FR-05** A reanálise dos campos a partir do texto guardado corre sem
  rede. — `reparsear()` / `--reler`
- **FR-06** O sistema relê até `relidos_por_volta` anúncios marcados com
  prazo aberto por verificação e regista alterações valor→valor de
  prazo e preço base em fila própria e no histórico. —
  `reler_marcados()`, `diferencas_do_detalhe()`, `registar_alteracoes()`
- **FR-07** Rectificações publicadas como anúncios novos são ligadas ao
  original pelo título, idempotentemente. — `ligar_retificacoes()`

**Peças e leitura por modelo**

- **FR-08** Ao marcar «interessa» (ou a pedido), o sistema descarrega o
  PDF oficial e as peças das plataformas acingov, vortal e JSF
  (anogov/ComprasPT/ESPAP por assinatura), em fila de fundo, para
  `documentos/<ref>/`. — `obter_documentos()`, `pedir_documentos()`
- **FR-09** Ficheiros acima de 60 MB não são descarregados; são
  nomeados no aviso e o estado fica «parcial». — `_descarregar()`,
  `MAX_FICHEIRO`
- **FR-10** O texto das peças é extraído com marcas de página, com
  estados distintos para digitalização, erro e não-PDF. —
  `extrair_textos()`, `texto_do_pdf()`, `texto_do_zip()`
- **FR-11** Um modelo lê apenas documentos públicos (CE e PC) e
  preenche objecto, localização/regime, equipa, documentos da proposta
  e preço anormalmente baixo, em três pedidos com recortes por âncoras
  (tecto 7 000 caracteres), registando fontes com páginas e o modelo
  que respondeu. — `analisar_pecas()`, `LEITURAS`, `_perguntar()`
- **FR-12** A leitura desce uma cadeia de fornecedores por ordem,
  saltando os esgotados no dia; o esgotamento diário só é anunciado
  quando toda a cadeia esgota. — `cadeia_de_fornecedores()`,
  `_ESGOTADOS`, `cadeia_esgotada()`
- **FR-13** Leituras parciais preservam campos, fontes e modelos das
  leituras anteriores. — `juntar_leituras()`, `juntar_fontes()`
- **FR-14** As âncoras e instruções de cada leitura são afináveis no
  `config.json`, com validação que mantém as de origem perante entradas
  inválidas. — `leituras_activas()` (B08)

**Filtros, alertas e triagem**

- **FR-15** Um filtro é uma query string com campos de ordem fixa, não
  pertence a nenhum separador, e cada vista aplica os campos que
  entende, declarando os que ficam de fora. — `CAMPOS_FILTRO`,
  `CAMPOS_POR_VISTA`, `filtro_actual()`, `filtro_para()`
- **FR-16** A pesquisa de texto corre sobre colunas normalizadas (sem
  acentos/maiúsculas) com o termo normalizado pela mesma norma da
  coluna; o LIKE escapa `%`/`_`. — `simplifica()`, `norma_entidade()`,
  `para_like()`, `condicoes()`, `condicoes_contratos()`
- **FR-17** O filtro de CPV aceita códigos e palavras da descrição
  oficial, com prefixos nunca abaixo de dois dígitos; inclui exclusões
  (`q_excl`, `cpv_excl`, em que exclusão vazia é não-filtro e NOT sobre
  NULL não esconde linhas por preencher) e modo E/OU entre palavras e
  CPV. — `prefixo_cpv()`, `cpv_por_termo()`, `frag_cpv`, B01/B07
- **FR-18** O estado da triagem entra sempre no filtro dos anúncios:
  ausente é «por ver», vazio é «todos». — `condicoes()`,
  `filtro_actual()`, `alerta_criar()`
- **FR-19** Um alerta é um filtro com a marca posta; o reconhecimento
  (pós-detalhes, com o motor da lista) é separado do envio; o acervo
  existente é marcado ao ligar. — `registar_alertas()`,
  `alerta_trocar()`, `ACERVO`
- **FR-20** O resumo diário sai uma vez por dia a partir da hora
  configurada, por e-mail quando configurado e sempre para
  `AVISOS.txt`; sem canal, o ficheiro conta como entrega; falhas reais
  de envio não marcam como enviado. — `enviar_resumo()`,
  `texto_do_resumo()`, `enviar_email()`
- **FR-21** Cada alerta mostra a taxa de acerto sobre os triados que
  marcou. — `/alertas` (B06)
- **FR-22** Entidades com NIF podem ser seguidas; os anúncios novos
  delas (casados por NIPC) entram no resumo com acervo próprio. —
  `entidades_seguidas`, `registar_seguidas()` (B10)
- **FR-23** Filtros guardados aplicam-se por ligação (leitura), gravam
  por cima pelo nome com confirmação, e a árvore de CPV semeia-se do
  filtro em uso. — `caixa_de_filtros()`, `gravar_filtro()`,
  `arvoreSemear()`

**Corpus e inteligência de mercado**

- **FR-24** O corpus de contratos vive em ficheiro próprio, importado
  do dump semanal do IMPIC com endereço resolvido pela API do dados.gov
  a cada importação; reimportar um ano substitui-o. —
  `importar_contratos()`, `recursos_contratos()`
- **FR-25** A identidade de uma entidade é o NIF (ou `n:`+nome
  normalizado); todas as agregações e filtros de entidade usam a chave,
  nunca o nome; o nome canónico é o mais usado. — `chave_entidade()`,
  `resolver_entidades()`, `entidade_do_anuncio()`
- **FR-26** A lista de contratos só aparece com filtro; os gráficos
  correm sobre o filtro da lista, pedidos ao abrir, desenhados em
  Python como HTML. — `contratos()`, `resumo_contratos()`,
  `/contratos/resumo`
- **FR-27** O valor de um contrato ganho por agrupamento reparte-se
  pelos adjudicatários; o desconto agrega por procedimento
  (`n_anuncio`), excluindo bases ambíguas. — `n_adj`,
  `descontos_por_procedimento()` (B04)
- **FR-28** As renovações são os contratos vistos pelo fim estimado
  (celebração + prazo), com janela por whitelist e a estimativa
  declarada no ecrã. — `/renovacoes`, `fim_estimado()` (B03)
- **FR-29** A ficha do anúncio cruza com o corpus: histórico da
  entidade restrito ao CPV, referência de preço (mediana/quartis com
  mínimos), desconto mediano, e procedimentos homólogos por termos do
  título (≥2 em comum). — `mercado()`, `referencia_de_preco()`,
  `homologos_do_anuncio()` (B02)
- **FR-30** A ficha de entidade mostra os dois papéis (compra/ganha)
  com filtro próprio somado à entidade em todos os blocos. —
  `ficha_entidade()`, `filtros_da_ficha()`

**Painel e apresentação**

- **FR-31** O quadro kanban contém apenas anúncios «interessa», com
  fases editáveis (semeadas uma vez, nunca sobrepostas às do
  utilizador), etiquetas globais e soma de preços base por coluna. —
  `/quadro*`, `semear_fases()`, `soma_precos_base()` (B11)
- **FR-32** O calendário mostra 45 dias com dias da semana,
  fins-de-semana e fronteiras de mês; prazos fora da janela são
  contados numa nota. — `/calendario`
- **FR-33** Os indicadores calculam tudo por SQL local; cada número com
  limiar abre exactamente a lista que o confirma, com a mesma janela
  (`janela_urgente`, `dias_urgente` configurável 1–90). —
  `/indicadores` (B13)
- **FR-34** Datas guardam-se ISO e mostram-se DD/MM/AAAA (CSV
  incluído); números com espaço inquebrável; truncagem visível com
  reticências; CSV com vírgula decimal e data no nome. — `data_pt()`,
  `data_hora_pt()`, `mil_pt()`, `corta()`, `numero_csv()`, `nome_csv()`
- **FR-35** Toda a acção que altera dados é POST; a volta preserva
  filtro, página e posição de scroll; destinos de redirect vindos de
  formulários são validados. — `accao()`, `volta_a_lista()`,
  `volta_para()`, `LISTA_JS`
- **FR-36** A identidade do utilizador é um cookie sem palavra-passe;
  acções ficam no histórico com autor (explícito no trabalho de
  fundo). — `quem_sou()`, `registar()`
- **FR-37** A pesquisa nas peças (B09) está **excluída por decisão**:
  nem `q_pecas`, nem FTS, nem caixa na ficha; o `iniciar_db()` limpa o
  índice de quem o teve. — teste `TestPesquisaNasPecasRetirada`

**Operação**

- **FR-38** O sistema verifica sozinho às horas configuradas via
  tarefas do Windows; o relógio interno do painel recupera slots
  falhados; a falta das tarefas é avisada a vermelho. — `relogio()`,
  `tarefas_em_falta()`
- **FR-39** Antes da recolha faz-se uma cópia diária do `radar.db` por
  `VACUUM INTO`, com rotação de 7. — `copia_de_seguranca()`
- **FR-40** Trabalhos longos nunca correm dentro do pedido HTTP:
  verificação e corpus em thread com trinco e estado visível, peças e
  análise em filas; as páginas afectadas recarregam-se sozinhas até um
  estado terminal. — `comecar_verificacao()`, `actualizar_corpus()`,
  filas
- **FR-41** Documentos servidos ao browser ficam confinados à pasta do
  anúncio. — `servir_documento()`, `nome_seguro()`

### 6.2 Requisitos técnicos

- **RT-01** Uma aplicação local num ficheiro Python único; dependências:
  flask, requests, pypdf, cryptography; opcionalmente autocontida em
  pen (`python/`+`libs/`, `_python.bat`).
- **RT-02** SQLite em WAL com `busy_timeout` 30 s, ligação nova por
  operação, `simplifica()` registada na ligação; duas bases separadas
  (trabalho vs. corpus derivado), cruzadas por `ATTACH` quando preciso.
- **RT-03** Migrações idempotentes que correm a cada arranque
  (`CREATE IF NOT EXISTS`, `ALTER` condicionado a `PRAGMA table_info`,
  reparações únicas por marca em `estado`/`corpus_estado`); as do
  corpus correm também no arranque do painel.
- **RT-04** Acesso ao DR exclusivamente pelos `screenservices` com
  cabeçalhos/token de capturas cURL feitas à mão; pausas de 1 s entre
  pedidos; formatos `bash` e `cmd` entendidos, com reparação dos
  acentos comidos pelo `cmd` (`VALORES_FIXOS`).
- **RT-05** Inserções em massa constroem o SQL a partir das listas de
  colunas (`COLS_*`/`_inserir()`); nunca `VALUES (?,...)` posicional à
  mão.
- **RT-06** HTML gerado por concatenação com um só `CSS` e um só
  esqueleto (`BASE` + `envolver()`); CSS entra por substituição para
  não escapar `%`; JavaScript embutido, sem framework nem build; fontes
  Google com fallback de sistema.
- **RT-07** Orçamento de modelo: tecto por pedido dimensionado ao
  limite de tokens/minuto da conta (não ao contexto do modelo); três
  pedidos separados por concurso; nunca o documento inteiro.
- **RT-08** Testes sem rede e sem base, <1 s, um por regressão real;
  hooks de sessão compilam o Python escrito, travam commit com testes a
  falhar e recusam escritas nas capturas e na base.
- **RT-09** Git local sem remoto; `.gitignore` exclui dados, segredos,
  bases, cópias e o Python embutido; commit no fim de trabalho acabado.
- **RT-10** Segurança actual assumida: sem autenticação, sem CSRF, sem
  TLS — aceitável apenas enquanto `127.0.0.1` num PC de uma pessoa; a
  lista do que falta para partilhar está no ESTADO («Pessoas, e o
  caminho para isto ser partilhado») e mantém-se válida.

---

*Auditoria produzida por leitura de código e consultas só-leitura;
nenhuma linha de código, configuração ou dado foi alterada. Números de
desempenho citados são as medições registadas no ESTADO.md nas datas lá
indicadas; contagens de base de dados e de código são de 30/08/2026.*
