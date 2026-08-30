# Armilar — Análise de Mercado (benchmarker)

Observado a 30/08/2026. URL reveladora, aberta pelo botão "Insights detalhados"
da ficha CCP USSIC-22-2026:

    /benchmarker/market-analysis?locationIds=8437&categoryIds=28186
      &awardValueStart=10086.00&awardValueEnd=30258.00
      &awardDateStart=2024-08-29&awardDateEnd=2026-08-30&tab=0

## A mecânica dos "Insights" da ficha, exposta pela query string

O preço base do concurso era 20 172 €. O filtro pré-construído é:
- mesma categoria (CPV) e localização;
- valor da adjudicação entre **10 086 e 30 258** = preço base × 0,5 a × 1,5;
- adjudicações dos **últimos 2 anos**.

Ou seja: "potenciais concorrentes" = quem ganhou contratos semelhantes
(categoria + localização + valor ±50%) nos últimos 2 anos. (Inferido da query
string; a fórmula não é declarada em texto.)

## O que a página tem

- Abas: **Contratos / Principais Adjudicadores / Principais Concorrentes**
- Filtros: tipo de procedimento, tipo de contrato, categorias, compradores,
  valor da adjudicação (min/max), data, localizações ("Todas as Localizações
  (3718)"), fornecedores. Botões "Guardar como filtro" / "Meus filtros",
  "Pesquisar nos Meus Interesses", "Desbloquear critérios de pesquisa"
  (sugere que alguns critérios estão presos ao plano).
- Sidebar: Visão Geral, Análise de Mercado, Empresas seguidas, **Minha posição
  no mercado**.
- Exportar.

## Colunas da lista de contratos

Descrição/Referência, Data da Adjudicação, Adjudicado por, Adjudicado a,
Preço da Adjudicação, **Desconto**, **Número de licitadores**.

O filtro devolveu 225 contratos. Amostra: "Renovação Suporte Switchs Cisco"
(Município de Santa Cruz → MC Computadores, 16 982,46 €, desconto 0,47%,
1 licitador); CIM do Cávado → NovaverdeIT, 18 900 €, desconto 20,75%,
**3 licitadores**.

**Nota para o radar:** o número de licitadores não existe no dump do IMPIC
(registado no CONCORRENTES.md). A Armilar tem-no — origem não declarada;
plausível (inferido): dados internos da plataforma Vortal e/ou anúncios de
adjudicação. O desconto é calculável no radar (preço base do anúncio vs valor
do contrato); o nº de licitadores não é, com as fontes actuais.
