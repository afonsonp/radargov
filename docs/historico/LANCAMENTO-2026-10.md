# O lançamento — 5 de outubro de 2026

**Instantâneo:** descreve o dia do anúncio público do Mira Gov (5/10/2026)
e não se edita. O que mudar depois corrige-se nos donos vivos.

Neste dia o lançamento fez-se **só no LinkedIn e no WhatsApp**, por decisão
dele. Os vídeos, a série e o funil ficaram em pausa (§4–§6), até ele ver a
adesão.

---

## 1. O post do LinkedIn

A abertura é a história dele, contada por ele nesse dia. **A outra
plataforma não se nomeia**, em nenhum post nem comentário.

> Concorro a concursos públicos todos os dias.
>
> Desde maio que usava uma plataforma para isso. Era confusa, o acompanhamento das propostas estava sempre a dar erros e, às vezes, deixava de ler concursos — sem avisar. Num concurso público, um aviso que não chega é um prazo que se perde.
>
> Fartei-me e fiz a minha, com o que a minha experiência me dizia que fazia falta. Chama-se **Mira Gov**, e hoje abro-a a outras empresas.
>
> O que faz:
> → Lê o Diário da República de hora a hora e mostra só os concursos da sua área
> → Descarrega as peças e lê-as por IA: a equipa pedida, os documentos a entregar, a caução, as condições de pagamento — cada linha com a página de onde veio, para confirmar no original
> → Mostra o que cada entidade costuma pagar e quem costuma ganhar, a partir dos contratos do Portal BASE
> → Organiza a equipa: cada proposta fase a fase, os prazos e as tarefas de cada pessoa
>
> A decisão de concorrer continua a ser sua. O Mira Gov tira-lhe o trabalho de procurar.
>
> Pode vê-lo por dentro, sem conta, numa visita guiada com uma empresa de exemplo.
>
> Para começar, **10 lugares de fundador**: o plano Duo (duas pessoas) a 55 €/mês + IVA, sem pagar nada até 31 de dezembro. Em troca, peço-lhe a sua opinião franca sobre o que falta.
>
> Ligações no primeiro comentário 👇
>
> #contratacaopublica #concursospublicos #pme #portugal

**Primeiro comentário** (o LinkedIn mostra menos uma publicação com
ligações no texto):

> Visita guiada: https://miragov.pt/demo?utm_source=linkedin
> Pedir um lugar de fundador: https://miragov.pt/?utm_source=linkedin#acesso

## 2. O WhatsApp

**Amigos e família** (para reencaminharem):

> Pessoal, hoje lancei o projeto em que tenho andado a trabalhar 🚀
>
> Chama-se *Mira Gov*: ajuda empresas que concorrem a concursos públicos a encontrar os da sua área, lê os documentos por IA e mostra quem costuma ganhar e a que preço.
>
> Se conhecerem alguém numa empresa que concorre ao Estado (obras, serviços, fornecimentos…), reencaminhem-lhe isto, por favor 🙏
>
> Dá para ver por dentro sem criar conta: https://miragov.pt/demo?utm_source=whatsapp

**Grupos profissionais:**

> Bom dia a todos. Partilho um projeto que lancei hoje, para quem trabalha com contratação pública:
>
> *Mira Gov* — https://miragov.pt/?utm_source=whatsapp
> • os concursos do Diário da República da sua área, verificados de hora a hora
> • as peças descarregadas e lidas por IA, com a página de onde vem cada linha
> • o que cada entidade costuma pagar e quem costuma ganhar (Portal BASE)
>
> Visita guiada, sem conta: https://miragov.pt/demo?utm_source=whatsapp
>
> Há 10 lugares de fundador, sem pagar até 31 de dezembro. Se fizer sentido para a vossa empresa, digam-me e mostro-vos com os concursos da vossa área.

Os `utm_source` vêem-se na página das visitas (`/plataforma/visitas`): é
assim que se sabe de onde vieram os pedidos.

## 3. O que mudou no produto nesse dia

- **v2.0.59** — o `/demo`, a primeira versão: uma galeria de oito ecrãs com
  legendas. Não era o que ele queria.
- **v2.0.60** — o `/demo` passa a **visita guiada dentro da aplicação**, à
  maneira da demo da SpotGov (Navattic): a aplicação em ecrã inteiro, com
  uma empresa inventada, e um balão que leva a pessoa por onze passos;
  carregar no destacado avança. Os ecrãs gera-os o `ferramentas/demo.py`, e
  o `actualizar.sh` refá-los a cada actualização.
- **v2.0.61** — a caixa da pesquisa diz só «Procurar».
- O `llms.txt` passou a dizer que os planos Solo, Duo e Corporate estão
  indisponíveis até haver pagamentos, e que o que há é a oferta de fundador.
- O kit do dia (`~/radar-capturas/lancamento-2026-09-30/kit-5-outubro.md`,
  fora do git) foi conferido com o site: o anual é **um mês grátis** — o kit
  dizia «um mês e meio», com 408 € e 780 €, e são 429 € e 825 € —, e as
  respostas sobre preços passaram a falar da oferta de fundador.

## 4. Em pausa: vídeos com a cara dele, sem custo

Testado nesse dia, para reels do Instagram pessoal dele, automáticos e
gratuitos:

| Peça | Resultado do teste |
|---|---|
| Voz | **Funciona.** Edge TTS, voz `pt-PT-DuarteNeural`, sem conta |
| Cara a falar (foto + áudio) | **Funciona** no Space `multimodalart/MoDA-fast-talking-head`: 8 s de vídeo em 16 s, a 264×264 — serve num círculo, não em ecrã inteiro |
| SadTalker, Hallo, XTTS | Partidos (erro de construção ou de execução no Hugging Face) |
| LivePortrait, LatentSync | A correr, mas precisam de um vídeo, não de uma fotografia |
| Quota | **A quota anónima de GPU acabou depois de um vídeo.** É preciso uma conta gratuita no Hugging Face e um token |

O plano que ficou: a cara só no início e no fim (3–5 s); o meio com imagens
do Pexels (chave gratuita), cartões animados em HTML com as cores do Mira
Gov e o ecrã do `/demo` gravado sozinho; montagem com o ffmpeg. Nos vídeos
com a cara gerada, o rótulo «Informações de IA» do Instagram.

## 5. Em pausa: a série «o que descobri»

Não anúncios: a experiência dele, na primeira pessoa, com **um número real
por episódio** e nada inventado. A receita, igual em todos:

1. **Gancho** (0–3 s) — ele, uma frase de quem descobriu algo
2. **Contexto** (3–8 s) — o problema, em palavras de quem concorre
3. **O que descobri** (8–18 s) — o ecrã e o número, com a fonte
4. **O que aprendi** (18–24 s) — uma lição útil mesmo sem o Mira Gov
5. **Fecho** (24–27 s) — «Estou a construir isto. Vê em miragov.pt/demo»

Público: donos e gestores de PME que concorrem ao Estado (obras, AVAC,
manutenção, limpeza, serviços, fornecimentos) e quem lhes prepara as
propostas.

Números já medidos nesse dia (contratos do Portal BASE de 2023 a 2025; um
contrato com CPV de duas divisões conta nas duas, por isso os totais não se
somam):

| Por número de contratos | | Por valor | |
|---|---|---|---|
| 33 · Saúde (equipamento, medicamentos) | 209 340 | 45 · Construção | 18 893 M€ |
| 45 · Construção | 42 900 | 33 · Saúde | 10 356 M€ |
| 79 · Serviços a empresas | 40 921 | 09 · Combustíveis e electricidade | 2 942 M€ |
| 50 · Reparação e manutenção | 30 724 | 34 · Equipamento de transporte | 2 648 M€ |
| 71 · Arquitectura e engenharia | 28 176 | 90 · Resíduos e limpeza | 2 542 M€ |

Outros temas com dados já medidos: as quatro plataformas com 99% das peças;
os 28% dos anúncios na banda do DL 177/2026; as 70 leituras julgadas por
quatro perfis; os ajustes directos que o BASE mostra e o DR não; os
contratos a acabar.

## 6. Em pausa: o funil

Ele mandou, nesse dia, um reel e um Canva com o funil de uma empresa de
software B2B americana (seis níveis: tráfego, página, qualificação,
marcação, pré-chamada, medição). O que se tirou para o Mira Gov:

- **Já existe:** a qualificação (o pedido de acesso, que ele aceita, recusa
  ou põe em espera) e a medição (as visitas, com a origem e os UTM, sem
  cookies).
- **Proposto:** a marcação de demonstrações num calendário gratuito no
  `/demo` e no site; uma mensagem automática antes da demonstração com o
  `/demo` e a oferta de fundador.
- **A isca «comenta CÂMARA + concelho»**: responde-se com quanto essa
  Câmara gastou em contratos do sector da pessoa, a partir do BASE.
- **As palavras dos clientes viram anúncios**: as objecções do
  `MULTIDAO.md` e das demonstrações tornam-se episódios da série.
- **Não:** píxeis e cookies de anúncios, que contrariam a decisão de 4/10.
