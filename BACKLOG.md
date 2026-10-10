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


## O que está ABERTO

**Vinte.** Tudo o resto neste ficheiro é história — está feito, ou
está na lista do que não se faz. Invertido a 19/09/2026, a pedido
dele: «o Backlog começa por coisas que já estão terminadas».

| # | O que falta | Estado | Espera por |
|---|---|---|---|
| AMB | **Ambientes: o live (o que o cliente vê) separado do que se desenvolve e ensaia** (pedido dele a 4/10/2026: «depois do lançamento quero fazer manutenção evolutiva e correctiva sem mexer no que o cliente vê; várias releases por dia tem de acabar») | **Em pausa por ordem dele, só proposta, nenhum código.** Hoje o ambiente é a pasta onde corre o `radar.py` (`BASE_DIR`, a `PORTA` fixa; a única variável de ambiente é `RADAR_EMAIL_SENHA`). A instalação já só avança por tag, por isso o `master` já não é o live; faltam um sítio para correr o `master` e uma regra de cadência. **Proposta**: **live** = `miragov.pt`, a última tag, porta 8765; **dev** = `dev.miragov.pt`, o `master` sobre cópia das bases, porta 8799, só ele (Cloudflare Access); **testes** = a bateria, mais, quando houver testers, `testes.miragov.pt` (porta 8798, dados fictícios, Access com a lista deles). Tudo pelo túnel que já existe: um CNAME `*.miragov.pt` e uma regra de entrada por nome no `tunel_fixo.sh`; o isolamento está nos processos e nas pastas, não na Cloudflare, e correm todos no mesmo PC (uma cópia das bases são ~14 GB). **Peças**: (1) uma variável de ambiente com a pasta de dados e outra com o ambiente (produção por omissão; no ensaio a porta 8799, sem correio, sem recolha do DR, sem modelo nem BASE, uma faixa «ENSAIO» em todas as páginas e o `endereco_publico` próprio, para o `ao_endereco_certo()` e os links do e-mail não o mandarem para o `miragov.pt`); (2) o ensaio como portão da release — copiar as bases do live, arrancar o `master` por cima, correr as migrações — exigido pelo `antes_da_release.py`; (3) a versão (tag) visível no rodapé ou na saúde, se ainda não estiver; (4) a regra no `CLAUDE.md`: só se corta release no dia combinado, e um merge para o `master` deixa de implicar release. **Cadência**: uma release por semana, de manhã cedo (o `actualizar.sh` reinicia o painel); **hotfix** só para o cliente sem trabalhar, dados errados ou perdidos, ou segurança — feito a partir da tag em produção, sai como `vX.Y.Z+1` e depois entra também no `master`; **o que leve migração de base nunca é hotfix**. Passos dele na Cloudflare: o CNAME `*` e a Access do `dev`. Rejeitada: abrir a porta na rede de casa (o `acesso_livre_local` deixaria entrar sem login quem parecesse local, com cópias de dados de clientes) | **Afonso retomar**, e dizer o **dia da release** (a proposta era terça de manhã; semanal ou quinzenal), que entra na regra do `CLAUDE.md`. Depois, uma sessão para o (1) e o (4), e outra para o túnel e o ensaio |
| MCP | **Ligar o Mira Gov ao Claude de cada empresa** (pedido dele a 4/10/2026: «gosto da ideia de mcp»; desenho e decisões dele a 10/10/2026: todos os planos, o Claude primeiro e o ChatGPT só quando um cliente o pedir, só o redirect `claude.ai` na lista branca, a conta do dono fora, sem contactos, notas nem documentos do cofre mas com as peças, tokens que caem também ao trocar a palavra-passe, tecto de 30/min e 600/dia por conta e 2 000/dia por empresa, qualquer conta com o seu token) | **Meio feito a 10/10/2026** (ramo `claude/mcp-conector`; o que é está no `docs/FUNCIONAL.md` §4.11): o `/mcp` (JSON-RPC: `initialize`, `ping`, `tools/list`, `tools/call`, `prompts/list`, `prompts/get`; 401 com o `WWW-Authenticate`; o `Origin`), as nove ferramentas só de leitura com o `ler_peca` (páginas inteiras até ~120 mil caracteres por chamada, com a continuação) e os prompts «Explica-me este concurso» e «Ler as peças», as instruções do servidor que mandam ler as peças sempre que se fala de um concurso, o OAuth sem ecrã (metadados, registo dinâmico com a lista branca, código de 60 s com PKCE `S256`, refresh rodado que revoga a família ao ser reutilizado), as tabelas no `contas.py` (só resumos), o registo `chamadas_mcp` e o tecto, a revogação, e o `TestConectorMCP`. **Falta, por esta ordem:** (1) **o ecrã do consentimento**, `GET`/`POST /oauth/autorizar` — é HTML e espera pelo D1: sem sessão vai ao `/entrar?para=…` (com o segundo factor de sempre); com sessão chama o `mcp_servidor.validar_autorizacao()` (um `mostrar` desenha-se, um `voltar` redirecciona), mostra «O Claude (`anfitriao`) vai poder **ler** os concursos, as propostas e o mercado da [empresa], em nome de [e-mail]. Não pode alterar nada.», e o POST (com o CSRF da sessão, os campos do pedido escondidos e revalidados) chama o `emitir_codigo()` ou o `recusa_do_consentimento()` e redirecciona; regista no histórico da empresa «X ligou o Claude ao Mira Gov» (dentro de `com_empresa()`, se a rota for aberta). **Requisitos da revisão de segurança (M2, 10/10/2026):** mostra a conta e a empresa; «Claude (claude.ai)» é texto fixo, e o `client_name` (que quem regista escolhe) só aparece como detalhe e escapado; o código emite-se só por POST com o CSRF, e o GET só mostra; confirmar que herda o `X-Frame-Options` (o ecrã não pode abrir dentro de outro site); o `state` já está limitado a 512 caracteres no `validar_autorizacao()` (`TAMANHO_DO_STATE`); (2) **a linha «Assistentes ligados»** em Configurações › Conta (desde quando, último uso, «Desligar» pelo `contas.revogar_familia_mcp()`), e o gestor vê os da empresa na `/actividade`; (3) **a página da Ajuda** com o passo a passo (Claude › Definições › Conectores › «Add custom connector», `https://miragov.pt/mcp`); (4) **os termos e a privacidade** (decisão 10: os dados vão para a Anthropic a pedido da empresa); (5) **o ensaio com o Claude verdadeiro** (Free ou Pro): a versão do protocolo que ele fala, se a Cloudflare desafia os POST dos servidores dele (`160.79.104.0/21`), a pergunta de Lisboa, e **se o Claude aceita uma resposta do `ler_peca` com ~120 mil caracteres** (o texto vai só no `content`; se for grande demais, baixa-se o `CARACTERES_POR_CHAMADA`) | **Afonso**, o D1 e o ecrã do consentimento; depois o ensaio |
| EN | **O Mira Gov em inglês** (pedido dele a 8/10/2026: «eventualmente temos de disponibilizar o mira em inglês também») | Por partes, do mais barato ao mais caro: (1) **o site em inglês** (`miragov.pt/en`) — pouco texto, não toca na aplicação, e serve quem chega pelo Reddit (r/procurement, r/SideProject) e pelo LinkedIn de fora; (2) **a aplicação, só se houver procura** — os textos estão espalhados pelo HTML por concatenação do `radar.py` (ver o D1), e passá-los a um catálogo mexe em quase todos os ecrãs e testes, trabalho de semanas; (3) o que **não** se traduz sozinho: os anúncios, as peças e as entidades vêm do DR em português — um cliente de fora leria a interface em inglês e os concursos em português, a menos que se traduza por modelo, com custo por concurso. Para quem: empresas de outros países da UE que concorrem em Portugal, e consultores de concursos de fora | **Depois do D1** (decisão dele, 9/10/2026: «o EN só depois disto tudo»): uma sessão para o (1); o (2) e o (3) só com a palavra dele, depois de haver procura |
| DL177 | **Medir o efeito do DL 177/2026 na parte L** (pedido dele a 4/10/2026) | A ferramenta existe: `python ferramentas/mede_dl177.py` compara desde 1/10/2026 com as mesmas datas de 2025 e com setembro de 2026 — anúncios por dia, a fatia na faixa da consulta prévia nova (bens e serviços 75–130 mil €, obras 150 mil–1 M€), com preço base, com estimado, flexíveis. A primeira corrida (dois dias) está no `docs/diario/2026-10.md` e não conclui nada | **Uma sessão a 2/11/2026** (outubro inteiro) e **outra a 1/12/2026** (novembro): correr, escrever os números no diário, e dizer se a faixa encolheu |
| L3 | **Os grupos de tarefas por família** (`docs/historico/PLANO-2026-10.md`, §L3) | Decisão dele a 30/09/2026: «ainda não — tenho de investigar melhor»; a 1/10/2026 passou do plano para o backlog | **Afonso**, a investigação |
| L2-COB | **Cobrar: o que falta do L2 do plano de Outubro** (`docs/historico/PLANO-2026-10.md`, §L2; decisão dele a 1/10/2026: «para cobrar, põe no backlog») | O site já anuncia os planos e a oferta de fundador (v2.0.36), e até 31/12/2026 ninguém paga. Para a primeira fatura, em janeiro, falta: **L2.0** — a actividade aberta, o programa de facturação certificado, as referências Multibanco e os termos revistos por um advogado ou pelo contabilista (as sete dúvidas no fim do `docs/historico/TERMOS-2026-10.md`); **L2.1** — o plano como dado da plataforma (**Solo · Duo · Corporate**, decisão dele a 1/10/2026: saíram o Vigia e o VigIA+, e no mesmo dia o Equipa, de 5, deu lugar ao Duo, de 2 — «a equipa tem no máximo 2 utilizadores»; mensal e anual, o anual **pago de uma vez, sem reembolso** (decisão dele a 1/10/2026, que substituiu as 12 prestações). **Os preços são os do site** (confirmado por ele a 4/10/2026, e a linha antiga estava errada): Solo 39 €/mês ou 429 €/ano, Duo 75 €/mês ou 825 €/ano, e o fundador no Duo a 55 €/mês ou 605 €/ano); **L2.2** — os utilizadores contam (1 no Solo, com **uma só sessão de cada vez** — a última entrada fecha as outras e avisa —, 2 no Duo, o Corporate pelo número; feito na `v2.0.39`); **L2.3** — **saiu**: «todos os planos têm exactamente a mesma coisa, só muda o número de pessoas» (decisão dele a 1/10/2026) — a leitura por IA, as tarefas atribuídas, o Hoje por pessoa, as notas partilhadas e o cofre vão em todos; **L2.6** — as condições de pagamento, **por decidir**: os termos deixaram de as dizer a 5/10/2026 (diziam pré-pago com corte no próprio dia, e o financeiro da 6.ª ronda leu-o como incompatível com um pagamento a 30 dias), e nesse dia ele pediu **débito directo**, «não quero ninguém a usar a plataforma com pagamentos em atraso» — o que reabre a cobrança automática que o L2.4/L2.5 tinham tirado; **L2.7** — a página do dono com os dois avisos, e os e-mails. **Sem Checkout nem subscrição na Stripe** (o L2.4 e o L2.5 saíram a 30/09) | **Afonso** e o contabilista no L2.0; as sessões do L2.1 em diante só depois de 5/10/2026 |
| LANC | **O que o ensaio do lançamento pede ao site** (`docs/historico/MULTIDAO.md`, 30/09/2026) | O preço já está no site e as contradições de prazo e de utilizadores já não aparecem. **Por reconfirmar no site**: dizer que cada empresa tem a sua própria base e o que acontece aos dados se o vendedor parar (a 2.ª objecção, 142 em 500); e dizer à cabeça que os ajustes directos não aparecem (quem vive deles pede 3%) | **Afonso**, o texto; depois **uma sessão** |
| LANC-R | ~~**As regras do dono que faltam para o dia do anúncio**~~ — **decididas todas a 4/10/2026** (as de 30/09 e as que faltavam): o **NIF** não se pede no formulário (decisão dele a 4/10: os campos obrigatórios faziam desistir) e pede-se no Perfil da empresa, obrigatório só para passar a pago; **vagas**: 10 fundadores, depois ~20 empresas por semana, o resto em **lista de espera** com resposta no próprio dia (o «pôr em espera» entra no LANC-F); **consultas prévias**: entram, o site não promete o que o DR não publica; **uma conta por cliente**; **Corporate**: sob consulta, e **mais de duas pessoas é Corporate**; **compromisso de serviço**: nenhum número, só «resposta num dia útil»; **continuidade**: escrita nos termos e no site (#177); **parceiros com comissão: não, por agora** — volta com 5 ou mais clientes pagos; **demonstrações: sim** | *(o que se escreveu antes)* | — |
| LANC-F | ~~**O formulário do pedido e o ecrã do aceitar, à medida de um dia com muitos pedidos**~~ — **feito a 4/10/2026** (`TestOPedidoParaUmDiaComMuitos`): os oito pontos abaixo | **Já feitos antes**: o NIF (`nif_do_pedido()`, opcional desde 4/10), o aviso do mesmo e-mail (4/10) e o fundador (o plano «Oferta de fundador» ao aceitar). **Falta**: (1) um campo **opcional** «O que vende, e onde», que vai para a `mensagem` — o `perfil_do_pedido()` já lê dela os CPV e os distritos, e os cinco campos obrigatórios ficam; (2) o sector que engana (três engenharias escolheram TI): entra «Engenharia e projectos» (CPV 71000000) e «Tecnologias de informação» passa a «Software e informática»; (3) o aviso de repetidos também para a mesma pessoa noutra empresa (telemóvel ou nome) e para a mesma mensagem; (4) uma nota opcional no convite; (5) as regiões no `perfil_do_pedido()` pelo `DISTRITOS_POR_REGIAO` — «Centro» só com «região» ou «zona» antes; (6) recusar com uma caixa «avisar por e-mail», de texto fixo (o motivo fica só para o dono); (7) os tectos: 3 pedidos por e-mail por dia, os 5 por IP por hora, e o `PEDIDOS_POR_DIA` a 1000; (8) o **«pôr em espera»**, terceiro gesto nos pedidos, que avisa por e-mail sozinho | — |
| ANL | ~~**Os dados de uso: as visitas ao site e o uso da aplicação pelos clientes**~~ — **feito a 4/10/2026**: o site (`TestAsVisitasAoSite`, `TestOPainelDasVisitas`: sem cookies nem terceiros e sem guardar o IP, a tabela `visitas`, o beacon do `/visita`, o painel `/plataforma/visitas` e os pedidos ligados à visita de onde vieram) e a aplicação (`TestOUsoDaAplicacao`: a tabela `uso`, o cartão «Uso da aplicação» na página de cada empresa com os percursos começados e não acabados, só o dono vê); 13 meses, e a `site/privacidade.html` diz os dois | *(o que se escreveu antes)* | — |
| UX-7L | ~~**As dez correcções da auditoria das sete leis**~~ — **feito a 1/10/2026** (PR `claude/ux-lancamento`, `TestAsCorreccoesDeUXDoLancamento`): as dez da lista (o «Abandonar» neutro, os 44 px no toque, um primário por ecrã, o Calendário vazio que diz porquê, a falha da verificação só para o dono, os selos CLI/CONC neutros, a coluna «Falta» sem laranja, o prazo da ficha uma vez a laranja, o «comparar» por cima, o «A conta» fora do «Mais», a procura da entidade fora do Mercado, as datas do fim estimado sem negrito) e as outras que o relatório dizia caber (F4, H2, H6, H7, J8, M5, V8); e as dez da terceira auditoria (`UX-ECRAS-EM-FALTA-E-ESCURO.md`). **Ficou de fora, como os relatórios mandam**: ~~a pesquisa geral (J1)~~ (feita a 1/10/2026: a caixa da barra e o `/pesquisa`), ordenar nas tabelas do Mercado e das Entidades (J4), as abas do Mercado (J2), o gráfico repetido da Situação (M1), a Conta em três cartões (M2), os distritos por NUTS (M3), paginar as Entidades e esconder a coluna vazia (M4, E9), ~~o «docs 3/7» (G1)~~, ~~o repor por conta própria (J7)~~ (feito a 1/10/2026: o `/esqueci-me`), ~~o prazo e os passos da proposta sem anúncio (E6), a coluna da direita da ficha (E7)~~ e a ordem da ficha da entidade (E11, E12). **Saíram da lista a 1/10/2026**, por decisão dele («Faz todos»; PR `claude/ux-concursos`, `TestUXConcursosDe1Outubro`): os filtros dos Concursos recolhidos atrás do «Mais filtros» (H1), o prazo folgado neutro (V1), ordenar pelo preço nos Concursos e pelo prazo e pelo preço nas Propostas (J4), o calendário do browser nas datas dos filtros (J6), um só molde de cabeçalho (J3), o «→ fase seguinte» (H4) e as atrasadas no `<title>` (Z2) **Com o «Faz todos» dele (1/10/2026) fizeram-se também** as abas do Mercado (J2), o gráfico repetido da Situação (M1), a Conta em três cartões (M2), os distritos por região (M3), a paginação das Entidades e o «Lote» só quando há (M4, E9) e a ficha da entidade (E11, E12) — `TestUXMercadoDe1Outubro`; e o G1, o E6 (com a coluna `propostas.prazo_entrega`: a release que o levar pede cópia antes) e o E7 — `TestUXFichasDe1Outubro` | *(o que se escreveu antes)* | Cada um dos de fora pede a palavra dele | **Afonso** |
| UX-IDP | ~~**Ícones, dicas e pesos da letra**~~ — **feito a 1/10/2026**, com o UX-7L: as correcções 1 a 12 (a falha da verificação em palavras e com o sinal, a legenda CLI/CONC e o glossário, nenhum 700, um só tamanho de cabeçalho de tabela, o «?» do sistema, o responsável por extenso para o leitor, a colagem com a raiz a 16 px, os pequenos, a paginação e a fita com os ícones, os vazios com título, os atalhos à vista) e o `.sobre` do site a 600. **Ficaram de fora** as seis que o relatório diz que não cabem (13 a 18: os valores dos gráficos fora do `title`, ~~a sintaxe da pesquisa à vista~~, os títulos `h2` nos gráficos, o corpo das tabelas dos contratos a 14 px, ~~uma caixa de tarefa só~~, ~~a limpeza do CSS morto~~ — **feita a 1/10/2026**, `TestPesquisaGeralERepor`) e o número grande no telemóvel (C.2 #7, «perguntar») **Com o «Faz todos» dele (1/10/2026) fizeram-se também** o 13, o 15, o 16 e o C.2 #7 — `TestUXMercadoDe1Outubro`; e o 14 e o 17 — `TestUXFichasDe1Outubro` | *(o que se escreveu antes)* | — | — |
| FERR-E | ~~**O `ferramentas/ecrans.py` partiu-se com o multi-empresa**~~ — **feito a 1/10/2026**: vê as páginas da empresa como o gestor dela (`--empresa N`, a primeira por omissão) e as da plataforma como o dono, sem gravar sessão nenhuma; tem as Propostas, a Ajuda, os documentos da empresa, a `/plataforma` e os pedidos (a `/amostra`, que saiu, não); a entidade e a proposta sem anúncio vêm do corpus e da empresa, e sem nenhuma o ecrã não entra; a raiz fica nos 16 px e as fontes são as da aplicação (as Plex saíram de `tipo/`) | *(o que se escreveu antes)* | — | — |
| UX | **Auditoria pelas «leis de UX» (`docs/historico/UX-Auditoria.md`, 02/09/2026): repetir a medição do browser** | **P0 e os cinco P1 feitos a 02/09/2026** (contraste da coluna, alvos a 24 px, «desfazer» depois de triar, prazo neutro pós-submissão, fontes sem bloquear, quadro sem `reload()`); o resto saiu a 1/10/2026 (UX-7L, UX-IDP). **Falta repetir a medição do browser** sobre o resultado, que ninguém fez desde 2/09/2026 (era o D3) | **Uma sessão** |
| V1 | **Ligar um alerta ao interesse, e seguir entidades** | O `email.para` tem destino desde 16/09/2026 e o SMTP autentica, mas há **zero** alertas ligados e **zero** entidades seguidas: o resumo diário não tem o que dizer. É um gesto de duas Configurações — Alertas e a ficha de uma entidade | **Afonso.** Nada no código o impede |
| V2 | ~~**Julgar as 42 leituras com o `ensaio-de-leitura`**~~ — **feito**: quatro perfis julgaram as 70 leituras e houve segunda ronda a 29/09/2026 (`docs/historico/LEITURA-VALIDADA.md`) | *(o que se escreveu antes)* | — |
| D1 | **O HTML por concatenação de strings** | 39 722 linhas no `radar.py` (medido a 4/10/2026), mais de metade painel. É a maior dívida estrutural e está identificada desde a `AUDITORIA §3.9`; não era de nenhum plano e não estava escrita em lado nenhum vivo. Não é urgente — é o que torna cada ecrã novo mais caro que o anterior | **Em curso desde 9/10/2026, lote a lote** — o plano é o `docs/plano-d1.md` (moldes Jinja; cada lote passa o portão `ferramentas/igual.py` e o ensaio sobre a cópia das bases, e só entra no `master` com o ok dele). Fase 0 feita. **O EN só depois disto** |
| D2 | **Fundir os `_pecas_*` e trocar o `pypdf` pelo `pymupdf`** | Duas das três da auditoria ponytail de 14/09/2026, por decidir | **Afonso** |
| R2 | **O que o redesenho deixou cair de propósito, e é preciso olhar** | Duas coisas (eram três), todas por decisão do documento e não por esquecimento: a **ranhura saiu da linha de tarefa** (era do cabeçalho do grupo, que deixou de existir; a linha mostra ref · entidade · dono · entrega); o **adiar e o atribuir saíram da linha** para a ficha e para o `/tarefa/<id>/gravar` (a linha ficou com ✓ e desfazer) (o terceiro, o balde «Resto da semana» vazio ao fim-de-semana, deixou de existir a 29/09/2026: a fita começa ontem e o balde é «Próximos N dias») | **Afonso**, ao usar. Se alguma fizer falta, volta — a rota do `gravar` nunca saiu |
| R2 (perda do PC) | ~~Uma cópia do trabalho das empresas fora deste computador~~ | **Reaberta a 23/09/2026, por decisão**: com empresas clientes, nenhum dado vai para o GitHub, e a triagem deixou de lá ir (B15). Hoje o trabalho das empresas só existe no disco deste computador (`empresas/`, e as `copias/` no mesmo disco) | **Configurado a 24/09/2026**: o `copias_fora.sh` correu, o bucket está na UE, e um ficheiro de ensaio foi e voltou pela cifra. **Fechado a 25/09/2026**: a linha «Fora deste PC» diz «ok: 2026-09-25 08:00», e o B2 tem as cópias da empresa 2 e das contas |
| M1 | ~~**Mudar o nome para MiraGov**~~ — **feito**: o nome, a marca e os ecrãs na `v2.0.1` (24/09/2026); o domínio a 25/09/2026 (`miragov.pt`, com o `.com` e o `radargov.pt` a reencaminhar) | *(o que se escreveu antes)* | Ele já tem os domínios `.pt` e `.com`. É a próxima sessão, com retoques ao desenho: o túnel e o `endereco_publico` passam ao domínio novo, o `radargov.pt` redirecciona, e o nome muda no site, no logótipo, nos e-mails, nos textos legais e no manual. O código e a pasta podem manter o nome `radar` | **A próxima sessão** |
| Q1 | **O distrito e o preço base no interesse do Mercado** (teste com dez perfis de utilizador, 25/09/2026) | Na `v2.0.6` o interesse ganhou distritos e um preço mínimo, mas só recortam os **anúncios**: os contratos do Portal BASE não trazem o distrito na mesma forma (o `local_execucao` é texto livre), e o Mercado continua a recortar só por CPV | **Decisão dele a 25/09/2026: fica para o backlog** |
| Q2 | ~~**O preço e um contacto no site público**~~ — **feito**: o contacto a 28/09/2026 (`contacto@miragov.pt`) e o preço no site (Solo 39 €/mês, Duo 75 €/mês, os anuais, a oferta de fundador), confirmado a 4/10/2026 | *(o que se escreveu antes)* | — |
| Q3 | **A leitura das peças e a proposta, à medida do setor** (pedido dele a 25/09/2026) | Hoje a leitura pergunta o mesmo a todos os concursos, e a proposta pede os mesmos campos. Mas o que decide um *go/no go* muda com o setor: num concurso de **TI** a **equipa** pesa muito; numa **aquisição de bens** não há equipa — e sem equipa também não há **CV** a pedir. Falta **investigar, setor a setor, que informação é relevante** para decidir se se concorre (os critérios de adjudicação, a habilitação técnica, a equipa, os prazos de entrega, as certificações, as garantias…), e depois pôr a leitura do modelo e os campos da proposta (hoje `tipologia`, `cv`, `proposta_tecnica`) a variar com isso. **Faz parte dele, por investigar, a D6 da segunda ronda** (26/09/2026, o semáforo *go/no-go*): mostrar na ficha os requisitos que o DR já traz (o alvará com a categoria e a classe, a caução, as ponderações dos critérios); alargar as perguntas da leitura por IA aos **requisitos de habilitação** (alvará, caução, seguros, certificações — no teste afirmou mal «não fixa requisitos de equipa»); e o semáforo «Podemos concorrer?» contra o **cofre dos documentos** da empresa (Configurações › Documentos da empresa, feito a 26/09/2026). Decisão dele: «tem de ser melhor investigado» — **não se constrói agora** | **Investigado a 27/09/2026** (`docs/historico/SETORES.md`): o setor reconhece-se sem modelo, pelo tipo de contrato e o CPV; a caução e a habilitação já vêm no anúncio e a ficha não as mostra; e a leitura foi desenhada para 10% dos anúncios (0 equipas lidas em 17 empreitadas cujas peças falam todas do director de obra). Proposta em três degraus. **Afonso** decide as quatro perguntas da §6. **Segunda metade a 27/09/2026** (`docs/historico/CADERNOS.md`): com a prioridade dele (cabe na oferta? há capacidade? — a caução não conta), o que responde a cada pergunta, por família; o CE sozinho não chega (o que distingue está nos anexos e no Programa); e o Excel, onde vivem as quantidades, não se lê. **Desenho decidido a 27/09/2026** (`docs/historico/MAPA.md`): o Mira Gov **mapeia e a empresa decide** — sem GO; os 12 campos da skill dele, onze iguais para todos e o **11 conforme o tipo** (Equipa · Equipa técnica e alvará · Artigos e especificações · Postos e horários · Nível de serviço). Falta falar do código, do Excel e de reler as 70 leituras |
| 2R-D4 | **Anexos na proposta, por ligação externa** (D4 da segunda ronda, 26/09/2026: o recibo da submissão, a proposta entregue, o relatório, a pronúncia) | Decisão dele: a opção **(c)** — só uma ligação para onde o ficheiro já está (a pasta partilhada da empresa, a plataforma), e **não** ficheiros guardados no Mira Gov: esses pediam armazenamento por empresa e cópias que os cobrissem | **Uma sessão**. Pequeno: uma lista de ligações por proposta, como as notas datadas |
| 2R-D18 | **«Pedir opinião a…»** (D18 da segunda ronda: o comercial quer a opinião do chefe sobre um concurso que ainda não tem «Interessa») | Decisão dele: a opção **(c)** — um gesto na ficha que cria uma **tarefa para essa pessoa**, com a nota escrita, em vez de notas soltas no anúncio. O mecanismo das tarefas já existe (`criar_tarefa()` com `quem`) | **Uma sessão** |
| 2R-D20 | **As interacções com os contactos** («liguei a 25/09…», e o próximo contacto) | Decisão dele: a opção **(b)** — um registo por contacto que entra também no histórico da proposta. **Depois das notas datadas** (26/09/2026), que lhe dão a forma: texto, quem, quando | **Uma sessão** |
| 2R-D8 | ~~**Pesquisa global (Ctrl+K)**: concurso, proposta, entidade, NIF numa caixa só~~ — **feito a 1/10/2026** (PR `claude/ux-pesquisa`, `TestPesquisaGeralERepor`): o índice é `trigram`, e por isso «vigilância» continua a achar a «videovigilância» — a troca de baixo **não se fez** | Decisão dele: a opção **(b)**, **depois de um índice de texto** — sem ele cada tecla varria os 210 mil anúncios. **A troca a saber antes de o fazer**: o FTS5 procura por palavras (e prefixos), e por isso deixa de achar «videovigilância» quando se procura «vigilância», que o `LIKE` de hoje acha | **Uma sessão**, com a medição do índice (tamanho e tempo) antes |
| 2R-D12c | **O calendário num feed iCal privado, por pessoa** (D12 da segunda ronda: «a minha agenda é o Outlook», o consultor) | Os três filtros, as tarefas no dia delas e a agenda do telemóvel estão feitos (26/09/2026, as opções (b) e (d)); o (c) é o passo a seguir: um endereço secreto por conta, só de leitura, com as nossas e as tarefas | **Uma sessão** |
| 2R-A11Y | **O que a declaração de acessibilidade ainda diz que falta** (`site/acessibilidade.html`, 26/09/2026) | Duas não conformidades: a grelha dos dias do calendário no computador sem estrutura de tabela (1.3.1) e o «+N» de um dia cheio com menos de 24 px de altura (2.5.8); e o tema escuro sem auditoria de contraste de ponta a ponta. (A contagem da árvore dos CPV e as siglas CLI/CONC já saíram da declaração.) **Quem corrigir uma, tira-a da declaração e muda-lhe a data** | **Uma sessão** |
| 2R-§7 | ~~**O resto da página do dono**~~ — **feito a 4/10/2026** (`TestORestoDaPaginaDoDono`): o emblema dos pedidos na barra, suspender, reactivar e tirar uma conta pelo suporte, o registo de actividade (`/actividade`, tabela `entradas`, 90 dias), «porque é que os alertas não avisaram» na ficha, o tecto mensal das leituras (`leituras_por_empresa_por_mes`), o `--exportar-empresa` e a nota interna. Antes já estavam o 2.º factor, a lista dos erros, criar a empresa pela interface, o (2), o (10), o registo dos envios e fechar uma sessão. Os «Depois» da §7 (aviso a todos os clientes, plano e fim do teste, resumo diário ao dono, risco de abandono) ficam para quando houver 5 ou mais clientes | *(o que se escreveu antes)* | — |
| D6 | **As cinco propostas de `docs/historico/CAMADAS.md`** (19/09/2026) | A documentação medida contra o ICM: a camada 0 (`CLAUDE.md`) está **14× acima** do alvo do paper (~11 000 tokens contra ~800) e mistura três camadas; `docs/` junta 86 k de receita com 216 k de arquivo sem fronteira; e **este ficheiro** é estado de execução a fingir-se de referência — 32 linhas de tabela, **21 riscadas**, as seis primeiras todas feitas. **C1, C3 e C5 são baratos e independentes**; C2 e C4 mudam o mapa mental de quem trabalha aqui | **Afonso**, uma a uma. O C3 é este ficheiro: inverter, aberto primeiro |

---

## O que está FEITO, e o arquivo
### Registo de pendências — fechado a 31/08/2026

O que se fechou até 31/08/2026, com **quem** decidiu e **o que o
disparou**. (Era a lista do que estava em aberto; passou a história a
19/09/2026, quando o que resta subiu para o topo.)

| # | O que falta | Estado | Espera por |
|---|---|---|---|
| — | ~~Reler as peças pelo modelo quando chega um CE revisto~~ | **Feito a 14/09/2026**: a vigilância das peças voltou, por razão (data de esclarecimentos passada, prorrogação ou preço base novo) e por botão na ficha, avisa no resumo, e **com peça nova relê logo pelo modelo** (em linha na verificação, pela fila no botão) | — |
| E2 | ~~O primeiro envio do resumo diário~~ | **Feito a 31/08/2026, à ordem dele**: «Resumo enviado para [e-mail retirado]», com 1 anúncio do alerta CPV IT (INFARMED, 400 930 €). **Mas esta linha esteve errada de 8/09 a 16/09/2026**: o `--estado-zero` desse dia apagou o `email.para`, e o resumo deixou de sair para ninguém sem nada o dizer — reposto a 16/09 (D5 do `docs/historico/CICLOS.md`). Continuam **zero** alertas ligados e zero entidades seguidas: sem um deles, o resumo não tem o que dizer | — |
| E4 | ~~Registar quando o token expira~~ | **Feito a 31/08/2026**: cada expiração grava o momento e a idade da captura na série de erros (C3) e na marca dos indicadores | — |
| — | ~~Andamentos do esqueleto~~ | **Feitos a 31/08/2026** (1: navegação e âmbitos · 2: vocabulário e atalhos · 3: renovações fundidas em modo · 4: Fluxo B verificado e, com o E2, disparado — ver `docs/diario/2026-08.md`) | — |
| B15 | ~~Exportar a triagem~~ | **Feito a 31/08/2026**, e a sub-decisão do push também: **automático** («grava logo lá consoante o uso») — `empurrar_triagem()` faz commit+push só do `triagem.jsonl` em cada verificação em que mude; push falhado retoma na volta seguinte. **Isto fecha o R2 por inteiro**. **Desfeito a 23/09/2026** («no GitHub só código»): o push e o `triagem_no_git` saíram. A exportação ficou, por empresa e só local. O R2 volta a estar aberto (ver em baixo) | — |
| B14 | ~~Vortal como segunda fonte~~ | **Em produção desde 31/08/2026, com o âmbito dele**: só «GovPT - Consulta Preliminar», país PT, fonte='vortal' — zero duplicação com o DR. Primeira recolha: **17 consultas** (ver a secção B14). A acingov fica de fora: a listagem dela não distingue tipos sem abrir detalhes | Alargar a outros tipos não-DR ou à acingov: palavra dele, com medição antes |
| C3 | ~~Histórico de erros~~ | **Feito a 31/08/2026**: tabela `erros` com poda a 200 por tipo; as marcas continuam a servir o ecrã | — |
| — | ~~Fallback morto na detecção de plataforma~~ | **Medido e corrigido a 31/08/2026**: +28 anúncios com plataforma (todos acingov, dita por extenso no corpo); 56 → 28 sem plataforma | — |
| 11.7-B | ~~Procura directa de entidade~~ | **Feito a 31/08/2026, a pedido dele**: caixa «Ficha de entidade» em Mercado + `/entidade/procurar` — NIF vai directo, nome resolve por `entidade_nomes` (única → ficha; várias → escolha; nenhuma → di-lo) | — |
| — | ~~Visualizador de PDF na ficha~~ | **Feito a 31/08/2026, a pedido dele** (sai do «Não fazer»): os PDF das peças abrem em `/peca/<ref>/<nome>`, dentro da aplicação, com a pesquisa do próprio visualizador (Ctrl+F) — o caminho barato que estava anotado | — |
| CRM | ~~O «Em curso» não é um CRM: é a mesma consulta dos interessados~~ | **Plano escrito a 15/09/2026** e **reescrito no mesmo dia com as decisões dele**: `docs/historico/CRM.md`. Seis etapas. O desenho é dele — **uma escada só** (dez ranhuras: a entrada, as oito palavras da casa, o cemitério dos expirados), com lista, quadro e calendário como três vistas dessa escada | **Feito a 15/09/2026, as seis etapas**: as tabelas, a escada nas abas, a triagem a criar propostas, o quadro (que saiu no mesmo dia, por decisão dele: a ranhura muda-se no selector da linha), o calendário para qualquer ranhura, a navegação em Concursos · Calendário · Mercado, as tarefas que seguem as datas do DR, o ciclo fechado com o Portal BASE (por chave: o `n_anuncio` é o `ref`), os indicadores comerciais e os contactos. ~~Falta o NIF da casa~~ — **posto a 16/09/2026 por ele**: «LATD DIGITAL ENABLERS, LDA», NIF 516241362. O cruzamento com o Portal BASE deixou de perguntar e passou a dizer quando a adjudicação é nossa |
| B15-b | ~~Os campos do CRM não saem no `triagem.jsonl`~~ | **Fechado a 15/09/2026, sem trabalho próprio**: as colunas em falta são exactamente as que a etapa 1 do CRM apaga — exportá-las era escrever para deitar fora a seguir. A exportação faz-se uma vez, já sobre `propostas` e `tarefas`, dentro dessa etapa | — |

#### Reaberto a 16/09/2026, pela visita com três meses de uso a fingir

Corrigiu-se o que era avaria. Fica o que **não** se corrigiu, por ser
decisão dele ou trabalho de outra dimensão:

| # | O que falta | Estado | Espera por |
|---|---|---|---|
| M1 | ~~O `/contratos/resumo` leva 92 s a frio~~ | **Feito a 16/09/2026, sem cache nenhuma**: duas causas medidas e corrigidas na origem — o recorte por CPV passou de `LIKE` a `GLOB` (2,83 s → 0,03 s: o `LIKE` é insensível a maiúsculas e não usa o índice) e o «Quem ganha» ganhou um índice de cobertura `(contrato_id, chave)` (6,19 s → 1,02 s). **92 s → ~5 s**, e a página já estava atrás de um `<details>` com «a carregar…». As seis agregações sobre ~96 mil linhas são o que sobra | — |
| V1 | ~~«Casa» ainda é o vocabulário do código~~ | **Feito a 16/09/2026, a pedido dele.** Identificadores, o módulo (`casa.py` → `empresa.py`), a rota, a bandeira da consola e a documentação viva. E **duas migrações**, porque duas das coisas com esse nome estavam gravadas: as chaves `nome_da_casa`/`nif_da_casa` do `config.json` (que levam o NIF do cruzamento com o Portal BASE) e a tabela `casa` do `radar.db`. As duas idempotentes e guardadas por teste. O que fica com «casa» é português — «casar», «casamento», as «casas» de um CPV — e as páginas de história (`docs/diario/`, `docs/historico/`), que são registo do que se disse no dia | — |
| V2 | ~~O papel da entidade só aparece na ficha dela~~ | **Feito a 16/09/2026**: o selo entrou nas duas colunas do Mercado e nos três blocos da ficha que listam adjudicatários. Para o pagar, os dois totais passaram a viver na tabela `entidades` (`compra`, `ganha`), somados **com o corpus** e não a cada pedido — vinte contratos são vinte adjudicatários, e perguntar por cada um eram quarenta somas sobre 2 milhões de linhas por página. Na lista o selo é abreviado (`CLI` · `CONC` · `C+C`) e **não é a inicial**: «Cliente» e «Concorrente» começam os dois por C, e deixar a cor fazer o trabalho da palavra não se lê em voz alta nem sobrevive à daltonia | — |
| U1 | ~~A procura da lista das propostas não ignora acentos~~ | **Feito a 16/09/2026**, e **sem** coluna normalizada: são dezenas de linhas e o `simplifica()` já está registado como função da ligação (`liga()`), por isso `simplifica(titulo) LIKE ?` custa menos do que duas colunas para manter em cada escrita mais a migração que as enchia | — |
| U2 | ~~A linha da lista das propostas tem 90 px de altura~~ | **Feito a 16/09/2026**: `min-width` declarado nas duas colunas que quebram, e o título e o cliente cortados a duas linhas (`-webkit-line-clamp`), com o texto inteiro no `title`. **90 px → 57 px**, nove propostas por ecrã em vez de quatro, e todas as linhas **iguais** — que é o que faz as colunas alinharem. Nos quatro separadores com coluna «Proposto» a tabela rola 122 px dentro de si; o que fica de fora é o «abrir», mesmo destino do título | — |
| CICLOS | **Os caminhos não fecham**: o Hoje mostra 55 tarefas que só se resolvem uma a uma na ficha do anúncio; a ficha da entidade só existe pelo corpus e só se chega lá por um contrato; a proposta sem anúncio é só um formulário; a leitura que bateu no tecto do dia nunca se repete; e a documentação viva descreve o quadro, as quatro abas e a pen | **Plano escrito a 16/09/2026**, à noite, com as nove decisões dele respondidas: `docs/historico/CICLOS.md`. Cinco fases, um PR cada: tarefas · entidade · proposta e a condicionante da escada · peças · documentação. O `email.para` ficou posto nessa noite (estava vazio desde o estado zero de 8/09, e a linha do E2 acima dava-o como feito) | ~~A sessão seguinte~~ — **as cinco fases feitas a 17/09/2026**, cada uma com o seu commit e a sua linha no §9 do plano. Ver o `docs/diario/2026-09.md` desse dia |
| U3 | ~~Os campos de data mostram `mm/dd/yyyy`~~ | **Feito a 16/09/2026**: os quatro formulários passaram a campo de texto com `dd/mm/aaaa` e `pattern`, como o da data das tarefas já era. O `data_de_filtro()` lê as duas escritas (os atalhos de período continuam a pôr ISO no endereço) e recusa um dia que não existe; a legenda do filtro também deixou de dizer «desde 2026-01-01». **O que se perdeu foi o selector nativo** — os atalhos «12 meses · 3 anos · 2026…» são o caminho rápido e ficam | — |

#### Aberto a 17/09/2026, depois das cinco fases do CICLOS

O que ficou por fazer, com **quem** decide e **o que o dispara**.

| # | O que falta | Estado | Espera por |
|---|---|---|---|
| M2 | ~~A ficha de uma entidade com muitos anúncios leva ~1,3 s~~ | **Corrigido a 17/09/2026, na origem.** Ele apanhou-o a usar a aplicação («parece-me que está muito lenta»), e a medição lado a lado disse que era regressão minha: 0,33 s na v1.6.0 contra 1,63 s na v1.7.0. Faltavam os índices do filtro por entidade — **os dois**, porque com um só o SQLite não usa o MULTI-INDEX OR. 1,36 s → 0,01 s na consulta, e a página de volta aos 0,33 s. Ganha também a lista quando se filtra por entidade | — |
| R1 | ~~As Entidades, a ficha da entidade e os estados vazios do redesenho~~ | **Feitos a 17/09/2026, com os outros dois**: os cinco ecrãs do `docs/historico/REDESENHO.md` estão feitos — Hoje (§1), Ponto de situação (§2), Entidades (§3), ficha da entidade (§4) e os estados vazios (§5). O que ficou de fora do §3, por medida e não por esquecimento: as janelas de **24 meses** nas colunas «Compra» e «Ganha» da lista (são os totais de sempre, e dizê-lo na legenda custa menos do que uma agregação por entidade a cada página) e a coluna **«último anúncio»** (um `MAX(data_pub)` agrupado sobre 210 mil linhas por página). Na ficha, o «compra 24 m» existe — aí é uma entidade só | **Afonso**, se as duas colunas fizerem falta na lista |
| D4 | ~~**Os diagramas de `docs/`**~~ | **Resolvido a 19/09/2026 por decisão dele: apagados os seis.** Não era dívida de conteúdo, era de formato — 4,86 MB para 24 KB de conteúdo (**0,5%**; o resto é a biblioteca de desenho embutida em cada ficheiro), e cinco dos seis contradiziam o código **três dias** depois de gerados: a escada dizia «as oito palavras» no título quando são dez, a arquitectura rotulava o DR «a única fonte» havendo três, a recolha não tinha o passo da Vortal, e a porta não mencionava `origem_e_nossa()` uma única vez. Estão no histórico do git, o `.gitignore` trava o regresso, e o `CLAUDE.md` perdeu as seis linhas que avisavam do erro de cada um. **Geram-se quando se precisa, não se guardam** | — |


O que se abrir a seguir entra aqui com quem decide e o que dispara,
como sempre.

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
  de Mercado ser «a pergunta primeiro»: **nenhum painel dispara o
  resumo sem filtro** — regra de 30/08/2026, que sobreviveu ao
  documento que a escreveu.
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
  (base, corpus, peças). **Reaberta a 23/09/2026, por decisão**: com
  empresas clientes, nenhum dado vai para o GitHub. Hoje o trabalho das
  empresas só existe no disco deste computador (`empresas/`, e as
  `copias/` no mesmo disco). Falta uma cópia fora do PC que não seja o
  repositório de código — é a F6 do plano multi-empresa.
- **6.2-B (dois motores de filtro):** decidido mantê-los. Não é
  pendência, é decisão — reavaliável no andamento 3.

### P0

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

### P1

Vazio — B03, B04 e B05 feitos a 30/08/2026; ver «Feito», no fim.

### P2

- ~~**«Em curso» em modo lista**~~ (13/09/2026, do documento «Mudanças
  na plataforma RADAR»). **Feito a 14/09/2026** com as colunas que ele
  mandou: título, cliente, preço, esclarecimentos, entrega, tipologia
  (consulting/turnkey), estado da proposta (a fase), CV (sim/não),
  proposta técnica (sim/não), notas, plataforma, CoE, responsável.
  Em `/lista`, terceira vista do Em curso; as cinco colunas da casa são
  novas na base e gravam-se linha a linha.

Vazio — B06 a B10 feitos a 30/08/2026; ver «Feito», no fim.

#### Da auditoria ponytail (14/09/2026), por decidir pelo Afonso

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
  de medir sobre as peças reais em `pecas/`: no ensaio sintético o
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

### P3

Vazio — B11, B12 e B13 feitos a 30/08/2026; ver «Feito», no fim.
**O backlog da análise competitiva está fechado de P0 a P3.**

### Feito

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
  `dias_urgente()` lê o `empresas/<id>/config.json` (lixo/zero voltam a
  10) e TODOS os sítios leem dela — filtro, rótulos, cartão dos
  indicadores, saúde. Edita-se no painel, em Configurações › Alertas
  ("Janela do urgente"), com validação 1–90 à vista.

### Anotado no esqueleto de informação de 30/08/2026

> O documento saiu a 19/09/2026 (estava no arquivo, citado por
> ninguém, e descrevia um `radar.py` com 9 938 linhas). Está no
> histórico do git; o que dele vale hoje é o que está nesta lista.

- ~~Procura directa de entidade (nome ou NIF)~~ — **reaberta e feita a
  31/08/2026, a pedido dele**: caixa «Ficha de entidade» em Mercado e
  rota `/entidade/procurar`, exactamente como aqui estava desenhado —
  NIF vai directo (é a chave do corpus), nome resolve por
  `entidade_nomes` com `norma_entidade()`; resolução única abre a
  ficha, várias dão lista de escolha, nenhuma di-lo. Tinha ficado de
  fora do esqueleto por decisão dele (11.7-A), com a possibilidade
  registada — o registo serviu.

### Anotado no saneamento de 30/08/2026 — FEITO a 31/08/2026

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

### Aprovado pelo Afonso a 30/08/2026

> Desfeito a 23/09/2026: a triagem deixou de ir ao git; o que se segue
> sobre o B15 descreve o que ficou até essa data.

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

---

## Não fazer, e porquê

> **Isto não é história: é regra.** Cada linha é uma coisa que
> alguém vai propor outra vez, com a razão por que não se faz.

Decisões registadas com a observação que as sustenta. Reabrem-se se a
premissa mudar — com data e números novos.

- ~~Visualizador de PDF dentro da aplicação~~ — **saiu do «Não fazer»
  a 31/08/2026, a pedido dele, e está feito**: os PDF das peças abrem
  em `/peca/<ref>/<nome>`, dentro do painel, exactamente pelo caminho
  barato aqui anotado (um `<embed>` do ficheiro de `pecas/`; a
  pesquisa é o Ctrl+F do visualizador do browser). A caixa de pesquisa
  solta (B09) continua retirada — isto é a versão que ele queria.

- **Número de licitadores por concurso** — Armilar e SpotGov mostram-no;
  **não há fonte pública**: o dump do IMPIC não o traz (medido a 29/08) e o
  da Armilar vem presumivelmente dos dados internos da própria plataforma.
  Prometê-lo seria inventá-lo. **A premissa mudou a 30/09/2026**: o
  detalhe de cada contrato no Portal BASE devolve a lista dos concorrentes
  com NIF (`contestants`) — não está no dump, está a um pedido por
  contrato (`docs/FUNCIONAL.md` §8 e `docs/historico/CONCORRENTES-2026-09.md`,
  adenda 2). Reabre-se com decisão dele; não se construiu nada.
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
  menu de Configurações (`/configuracoes/…`, sete secções;
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
