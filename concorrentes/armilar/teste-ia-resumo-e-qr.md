# Armilar — teste da IA (resumo + Q&R) no CCP USSIC-22-2026

Observado a 30/08/2026, página /opportunities/summaries/75776.

## "Gerar resumo da oportunidade"

- Botão na ficha, sobre a lista de documentos. Ao carregar: "Estamos a gerar o
  resumo... pode levar alguns minutos. Avisá-lo-emos assim que estiver
  disponível." **Tempo observado: entre 1 e 3 minutos** (o painel foi
  verificado a intervalos; aos ~40 s ainda gerava, aos ~3 min estava pronto).
- O resumo abre em página própria com **versionamento** ("Versão do Resumo:
  Versão 1 - 30/08/2026 01:14", combobox — sugere que se pode regerar e
  comparar) e botão de imprimir.
- Layout: PDF das peças renderizado à esquerda (com pesquisa e zoom), resumo à
  direita, chat Q&R num painel flutuante.
- Secções do resumo: VISÃO GERAL, DATAS IMPORTANTES, CRITÉRIOS DE AVALIAÇÃO E
  DE ADJUDICAÇÃO, GARANTIAS E PENALIDADES, PLANOS DE PAGAMENTO.
- **Cada secção tem "Fonte:" com os PDFs e botões com os números de página**
  que sustentam o texto (ex.: db1e0e24(...).pdf, páginas 1,2,3,4,6 +5).
- Qualidade observada: a secção de garantias cita cláusulas e requisitos
  exactos ("Cláusula 3ª, n.º 1 e 2", "R.4, R.10, R.11, R.12", helpdesk
  "09h00 às 18h00 em dias úteis"). Confere com o CE mostrado ao lado.
- Aviso legal permanente: "As informações são geradas por IA e podem conter
  erros. Deve sempre validar as informações manualmente."

## Defeitos observados no resumo

1. **Markdown por renderizar**: `**proposta economicamente mais vantajosa**`,
   `### Requisitos adicionais` aparecem com os asteriscos e cardinais à letra,
   em várias secções.
2. **Repetição**: a secção PLANOS DE PAGAMento diz a mesma coisa três vezes
   (parágrafo corrido + dois bullets redundantes entre si).
3. **O painel Q&R nasce colapsado fora do ecrã** numa janela de 1745×777 — o
   lançador "Perguntar mais info..." fica cortado no canto inferior direito;
   foi preciso abri-lo por JavaScript. Num ecrã grande o chat é inutilizável
   sem dar com o botão meio escondido.

## Q&R com IA — perguntas concretas

**P1: "Que documentos devem constituir a proposta?"** — resposta em <20 s,
citando a **Cláusula 8ª do Programa de Procedimento**: a) declaração de
aceitação do CE (modelo do Anexo I, PDF "AnexoI_[designação_empresa].pdf");
b) declaração assinada com os atributos da proposta, preços individuais e
total (Anexo IV); c) memória descritiva e justificativa; d) outros documentos.
Mais requisitos adicionais (preços em euros, 2 casas decimais, sem IVA) e o
modo de submissão: plataforma acingov até às 23:59 do 9º dia contado do envio
do anúncio para o DR. Com ligação "Ver Fonte".

**P2: "O programa de concurso fixa um limiar de preço anormalmente baixo?"** —
resposta em <20 s: "o programa de concurso **não menciona explicitamente um
limiar fixo** para preço anormalmente baixo. No entanto, há detalhes sobre
como os preços devem ser apresentados..." — **não inventou**; comportamento
correcto, igual à decisão do radar de escrever "o Programa não fixa nenhum".

## Comparação directa com o radar

- A IA da Armilar lê as peças de facto (ao contrário da Vera/Tendios na conta
  gratuita, que não indexa as peças — ver CONCORRENTES.md 29/08).
- Vantagens dela sobre o radar: fontes com **número de página** clicável ao
  lado do PDF; chat livre sobre as peças; versionamento do resumo.
- Vantagens do radar: campos estruturados na ficha (equipa, documentos, PAB)
  sem esperar 1–3 min; correu no acervo todo; custo zero.
- As perguntas do Q&R são livres (o utilizador escreve o que quiser) — é a
  versão conversacional do item "perguntas configuráveis" visto na Tendios.
