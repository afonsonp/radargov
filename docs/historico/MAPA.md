# O mapa das peças: os 12 campos, e o 11 conforme o tipo

**27/09/2026. Decidido por ele**, depois do `SETORES.md` e do
`CADERNOS.md`. É o desenho, não o que está feito: **nada foi
construído**, e o código fala-se primeiro. Instantâneo: não se edita.
Quando o código existir, o que ele faz passa ao `docs/FUNCIONAL.md`.

## A regra que manda em tudo

**O Mira Gov mapeia; a empresa decide.** Não diz se o concurso «cabe na
oferta» nem se é GO — nas palavras dele: «eu quero mapear a informação
dos cadernos de encargos, anexos técnicos e programa de concurso para
entregar à empresa e eles poderem decidir». Nada de semáforos de
decisão, pontuações de adequação ou perfis da oferta da empresa.

## Os 12 campos

São os da skill `concurso-reader` dele, os mesmos que o
`essencial_do_anuncio()` já mostra. **Onze servem a todos os tipos de
contrato; o 11 muda com o tipo.**

| # | Campo | Igual para todos? |
|---|---|---|
| 1 | Nome do projecto | Sim |
| 2 | Entidade adjudicante | Sim |
| 3 | Critério de adjudicação | Sim |
| 4 | Preço base | Sim |
| 5 | Preço anormalmente baixo | Sim |
| 6 | Duração do contrato | Sim |
| 7 | **Local de execução** (era «Local de prestação de serviços», que não serve a uma obra nem a uma entrega) | Sim |
| 8 | Data de esclarecimentos | Sim |
| 9 | Data de submissão da proposta | Sim |
| 10 | Objecto, âmbito e características | Sim |
| **11** | **Muda com o tipo** — abaixo | **Não** |
| 12 | Documentos que constituem a proposta | Sim |

**O que a skill tem e o Mira Gov não leva:** o resumo com a
«oportunidade para a CONKORD», o Go/No-Go e o «No-Go automático». É
precisamente a decisão, que é da empresa.

## Como se entrega cada campo

- O **valor**, a **peça** e a **cláusula** de onde veio, e uma citação
  curta — para a empresa conferir no documento.
- Duas faltas, e não se confundem:
  - **«não consta»** — as peças foram lidas e o dado não está lá;
  - **«não lido»** — o dado está num ficheiro que o radar não lê (hoje,
    o Excel: `CADERNOS.md` §2), **com o nome do ficheiro**, para a
    empresa o abrir.
- Lê-se o **conjunto das peças** — anúncio, Programa, caderno de
  encargos e anexos técnicos —, não o documento que se chama «caderno de
  encargos» (`CADERNOS.md` §1). Em contradição entre peças, as duas
  versões, cada uma com a fonte (é a regra da skill).
- As regras duras da skill valem para todos os campos: copiar os nomes
  tal como estão, cada requisito numa linha, não interpretar, não
  acrescentar qualificadores, e «—» onde não houver exigência.

## O tipo

Reconhece-se sem modelo, pelo tipo de contrato do anúncio e pela
divisão do CPV — as cinco famílias do `SETORES.md` §2. Onde a regra não
chega, cai em «outros serviços».

## O campo 11, por tipo

### Serviços de TI, projectos, consultoria, formação — «Equipa»

Como hoje (`INSTRUCOES_EQUIPA`): um bloco por perfil, com o nome exacto,
formação, experiência geral e específica, certificações e outras
condições; e o bloco «Em conjunto, a equipa deve deter». Acrescenta-se
o que a leitura dos CE mostrou que está lá quase sempre: **as horas
máximas e o valor/hora de cada perfil**, quando o CE os traz (8 em 10).

### Obras — «Equipa técnica e alvará»

```
Alvará: categoria, subcategoria e classe tal como pedidas — ou —
Equipa técnica (um bloco por função):
  Função exacta (director de obra, técnico de segurança, …)
  Formação ou inscrição (Ordem dos Engenheiros, OET, …) — ou —
  Experiência: a expressão exacta — ou —
  Presença em obra — ou —
Obra civil ou com equipamento a fornecer e montar: qual equipamento — ou —
Mapa de quantidades: onde está — ou «não lido: <ficheiro>»
Condicionantes do local e horário — ou —
```

### Bens — «Artigos e especificações»

```
Um bloco por artigo ou lote:
  Designação exacta — quantidade (firme ou estimada)
  Características exigidas (uma por linha)
  Marca/modelo — e se admite «ou equivalente»
Entrega: prazo, e o local ou os locais
Garantia e assistência: meses; tempo de resposta — ou —
Instalação e formação — ou —
```

### Mão-de-obra (limpeza, vigilância, refeições) — «Postos e horários»

```
Um bloco por local ou posto:
  Local — número de pessoas — horário — dias
Equipas mínimas e supervisão — ou —
Habilitações: alvará (tipo), título profissional, formação obrigatória
Equipamentos e produtos a cargo — ou —
Regime dos trabalhadores e transmissão — ou —
```
Na limpeza, as horas costumam estar numa lista de preços em Excel: aí
o campo diz «não lido» com o nome do ficheiro.

### Outros serviços (manutenção, telecomunicações, seguros, eventos…) — «Nível de serviço»

```
Âmbito: equipamentos, sistemas ou coberturas — ou «não lido: <ficheiro>»
Tempos de resposta, por prioridade ou por local — ou —
Qualificações legais exigidas aos técnicos — ou —
Volume: bolsa de horas, quantidades — ou —
Datas fixas — ou —
```

## O que fica por decidir com ele

1. **O código** — o campo 11 por tipo na leitura e na ficha.
2. **O Excel** — ler os `.xls`/`.xlsx`, ou deixá-los como «não lido».
3. **As 70 leituras que já existem** foram feitas com a pergunta da
   equipa de TI: relê-las todas (gasta orçamento do modelo), ou só as
   que entrarem na escada.
