# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Este projecto é escrito e comentado em português. Escreve em português de
Portugal — código, comentários, mensagens de commit e respostas.

## O que é

Aplicação local em Python que vigia os anúncios de contratação pública da
**parte L da série II do Diário da República**, guarda-os em SQLite e
mostra-os num painel Flask em `http://localhost:8765`. Corre no PC do
Afonso, verifica sozinha às 09:00 e às 17:00 por tarefas do Windows, e não
depende de nada da empresa.

Substitui a Armilar (produto Vortal, 200 €/mês). O `ESTADO.md` é o diário
do projecto — **lê-o antes de mexer** e actualiza-o no fim de trabalho que
mude decisões ou números.

## Comandos

```bash
python radar.py                    # painel em http://localhost:8765
python radar.py --uma-vez          # verifica e sai (é o que as tarefas correm)
python radar.py --historico 730    # recolha extra de N dias; conta horas
python radar.py --reler            # reanalisa o texto já guardado, sem rede
python radar.py --ler-pecas [tudo] # manda as peças ao modelo; "tudo" refaz as já lidas
python radar.py --importar-cpv F   # carrega o vocabulário CPV (uma vez)
```

Testes — sem rede, sem base, correm em menos de um segundo:

```bash
python teste_radar.py                                    # todos
python teste_radar.py TestPrefixoCPV                     # uma classe
python teste_radar.py TestPrefixoCPV.test_divisao_normal # um teste
```

Os `.bat` são atalhos para o Afonso, não para desenvolvimento:
`instalar.bat` (pip), `iniciar.bat` (painel), `verificar.bat` (`--uma-vez`),
`agendar.bat` (cria as tarefas 09h/17h), `historico.bat` (gitk).

## Arquitectura

Tudo em **`radar.py`** (~3900 linhas), dividido por bandas com cabeçalho
`# ---`. A ordem do ficheiro é a ordem do fluxo:

1. **base** — `liga()`, `iniciar_db()`, `ler_config()`. SQLite, tabelas
   `anuncios`, `documentos`, `analise`, `fases`, `etiquetas`, `historico`,
   `cpv_dict`, `slots`, `estado`.
2. **captura** — `carregar_curl()` / `parse_curl()` lêem `curl_DR.txt` e
   `curl_detalhe.txt`, capturas cURL feitas à mão no DevTools.
3. **leitura** — `recolher()` pagina a pesquisa do portal;
   `ler_detalhes()` vai à página de cada anúncio buscar CPV, prazo e preço
   base; `campos_do_detalhe()` faz o parsing por secções numeradas.
4. **documentos** — `obter_documentos()` puxa as peças do procedimento das
   plataformas que o permitem (`PLATAFORMAS_COM_PECAS`: acingov, vortal,
   compraspt, anogov), por fila e thread de fundo. Ficam em `documentos/`
   no disco, **não na base** — para o `radar.db` ficar pequeno.
5. **leitura das peças por modelo** — `analisar_pecas()` recorta as zonas
   relevantes do CE/PC e faz três pedidos à Groq (um por campo), gravando
   em `analise`.
6. **painel** — rotas Flask, HTML gerado por concatenação de strings
   (`CSS`, `BASE`, `NAV`). Vistas: lista (`/`), ficha (`/anuncio/<ref>`),
   quadro kanban, calendário, indicadores.
7. **agendamento** — `relogio()`, thread daemon que dispara os slots.

### O que não é óbvio

- **Não se filtra nada à entrada.** Decisão tomada depois de uma primeira
  versão que filtrava por pontuação: entra tudo o que a parte L publicar, e
  a triagem faz-se no painel. Não reintroduzas filtros em `recolher()`.
- **O DR não tem API pública.** O radar faz-se passar pelo browser com os
  cabeçalhos e o token das capturas `curl_*.txt`. **O token expira** — o
  painel avisa a vermelho e o Afonso refaz a captura no DevTools (instruções
  na secção 3 do `LEIA-ME.md`). Nunca edites estas capturas: um hook
  bloqueia-o.
- **Orçamento do modelo, não contexto.** O tecto da conta Groq são 8000
  tokens/minuto, e é ele que manda no tamanho do pedido — daí
  `TECTO_RECORTE = 7000` caracteres e três pedidos separados em vez de um.
  Juntos, as âncoras do objecto gastavam o orçamento antes de chegar à
  tabela de perfis. Há também um tecto diário: `SEM_ORCAMENTO_HOJE`.
- **A chave da API** lê-se de `groq_API_KEY.txt` / `chave_api.txt` ou de
  `GROQ_API_KEY`. O `.gitignore` é deliberadamente largo (`*api_key*`,
  `*token*`, `*secret*`) porque a chave já apareceu com nomes diferentes.
- **Só passam pelo modelo documentos públicos** (Cadernos de Encargos e
  Programas de Concurso). Propostas, CVs e trabalho próprio não.
- **Migrações idempotentes.** Colunas novas acrescentam-se ao ciclo de
  `ALTER TABLE` em `iniciar_db()`, que corre sempre e não faz nada se já
  existirem. Não escrevas migrações que corram uma vez só.
- **Convenção de acentos:** comentários e docstrings do `radar.py` em ASCII,
  sem acentos; texto visível ao utilizador (HTML, prints, prompts) com
  acentos. Segue o que já lá está.
- **OneDrive.** A pasta está dentro do OneDrive; a sincronização pode
  bloquear o `radar.db` a meio de uma escrita. Se aparecerem erros de base
  bloqueada, é isso.

### Os testes são regressões

Cada classe de `teste_radar.py` corresponde a um erro que existiu mesmo, e
o comentário diz qual — "simplificar" um teste é normalmente voltar ao erro.
Correm em menos de um segundo: corre-os antes de gravar.

## Hooks e skill

`.claude/hooks/proteger_dados.py` (PreToolUse) recusa escritas em
`curl_*.txt` e `radar.db*`. `.claude/hooks/verificar_sintaxe.py` (PostToolUse)
compila o Python escrito com `-W error::SyntaxWarning`, porque os erros que
passaram despercebidos neste projecto foram todos de sintaxe e de escapes.

A skill `estado-radar` lê a base em modo só-leitura e diz quantos anúncios
há, quantos faltam ler e se as capturas ainda são válidas — funciona mesmo
com o `radar.py` a meio de uma alteração que não compila.

## Git

Repositório local, sem remoto. Commit no fim de cada trabalho acabado, sem
esperar autorização.
