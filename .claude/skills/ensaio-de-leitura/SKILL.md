---
name: ensaio-de-leitura
description: Põe a resposta do modelo ao lado do texto do documento de onde ela devia ter vindo, linha a linha, para julgar se a leitura das peças presta. Usar quando o Afonso quiser validar a qualidade da leitura de um concurso, desconfiar de um campo, ou antes de fechar a v1.
disable-model-invocation: true
---

# Ensaio de leitura

Confronta o que o modelo escreveu com o texto das peças:

```bash
python ".claude/skills/ensaio-de-leitura/ensaio.py" <ref> [--sem-modelo]
```

A `<ref>` é como aparece na ficha (`21295/2026`; também aceita `21295-2026`).

- **sem `--sem-modelo`**: relê as peças pelo modelo, **sobre uma cópia da
  base** — o `radar.db` não é tocado e o ensaio repete-se sem consequências.
  Custa ~6 mil tokens. É o que se usa depois de mexer nas instruções ou nas
  âncoras.
- **com `--sem-modelo`**: julga a análise que já está guardada. Não gasta nada
  e não escreve nada. É por aqui que se começa.

Mostra a saída ao Afonso sem a reformatar.

## Como ler o que sai

Cada linha da resposta leva uma marca e, por baixo, o pedaço do documento:

- **✓ literal** — a frase está no documento tal e qual. Nada a decidir.
- **~ reescrito** — todas as palavras estão lá, mas não seguidas: o modelo
  resumiu ou juntou pedaços. É o estado normal de um "objecto decomposto" bem
  feito. Vale a pena olhar para a janela mostrada e confirmar que é mesmo essa
  a passagem.
- **? sem apoio** — há termos que não aparecem no documento. **Não é acusação
  de invenção**: o caso mais comum é o modelo ter nominalizado um verbo
  ("Automatizar" → "Automatização"). A janela ao lado resolve a dúvida numa
  vista de olhos.

A comparação é feita sobre texto comprimido — sem acentos, sem maiúsculas, sem
espaços e sem pontuação — porque o extractor de PDF parte números ("1 2 meses")
e um grep ingénuo produzia uma acusação falsa. Está no ESTADO.md.

O texto confrontado é o **das peças inteiras**, não o recorte de 7 000
caracteres que o modelo viu. De propósito: apoio que exista no documento mas
esteja fora do recorte não é invenção, é recorte a apertar de mais — e as duas
coisas corrigem-se de maneiras diferentes.

## O que o guião não sabe julgar

Sabe dizer se o texto veio mesmo do documento. **Não sabe dizer se serve para
decidir** — e é essa a pergunta que falta para a v1. Ao ver a saída, perguntar:

- **Equipa**: estão lá os perfis *e* as quantidades, anos e certificações? Uma
  tabela de perfis lida pela metade é pior do que não ter lido nada, porque
  parece completa.
- **Objecto**: dá para perceber o que é preciso *fazer*, ou ficou pela remissão
  ("conforme o Anexo I")? Uma remissão é sinal de âncora a apanhar a zona
  errada.
- **Documentos da proposta**: é a lista fechada do artigo, ou só os primeiros?
- **Preço anormalmente baixo**: "não consta" aqui é uma resposta — o Programa
  pode mesmo não fixar limiar. Confirmar no documento antes de dar por errado.

Se um campo estiver mal, o sítio de mexer é a `LEITURAS` no `radar.py`
(âncoras e instrução por campo), não o modelo.
