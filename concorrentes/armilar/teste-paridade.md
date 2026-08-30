# Armilar — teste de paridade (30/08/2026)

3 anúncios do radar publicados a 28/08/2026, procurados na Armilar
(módulo "Alerta de Negócios", universo total de 11 378 004 oportunidades,
pesquisa com "Incluir todas as Palavras"):

| Radar | Armilar | Resultado |
|---|---|---|
| 21811/2026 UMinho, 20 172 € | CCP USSIC-22-2026 | **Encontrado**, mesma data (28/08), preço e prazo iguais |
| 21825/2026 ULS Sto António, 122 040 € | (título Vortal + título DR concatenados) | **Encontrado** ("vapor distribuição"), mesma data, prazo 16/09 22:59 |
| 21809/2026 Mun. Santo Tirso, E.M. 644, 872 214,20 € | — | **NÃO encontrado.** "Negrelos Roriz" e "Tomé Negrelos Campo" (AND; o título contém todas) devolvem obras antigas de Santo Tirso mas não esta, 2 dias após publicação. Causa indeterminada: falha de ingestão ou de indexação. É da plataforma vortal, como o da ULS que aparece. |

Inverso — 3 itens da Armilar procurados no radar.db: 3/3 encontrados, mesmas
datas de publicação:

| Armilar | Radar |
|---|---|
| RIC 452/2026, EM Ambiente do Porto, SOC/NIS2, 240 000 €, 03/08 | 19753/2026, 03/08 ✓ |
| CP/197/2026/SGMJ/CPVC, SG Min. Justiça, 111 806,58 €, 21/08 | 21318/2026, 21/08 ✓ |
| PD099/2026, IMPIC, manutenção do Portal BASE, 213 830 €, 25/08 | 21488/2026, 25/08 ✓ |

## Notas de pesquisa (grelha D/H)

- A pesquisa simples é **OR de palavras soltas, ordenada por data** — "equipamento
  de produção e distribuição de vapor" devolve 9 942 resultados com almoços
  protocolares de 18 € da Universitat de Girona no topo. Com "Incluir todas as
  Palavras" (AND) fica utilizável, mas a frase longa completa deu 0 mesmo
  estando no título (limite de termos? o "e"?). Não há aviso nenhum sobre isto.
- O universo inclui **micro-despesas adjudicadas** (dinners protocolares,
  reservas de hotel) — cobertura enorme, ruído enorme.
- "Meus Interesses" é o único sítio com a lista filtrada pelo perfil da conta
  (33 categorias/27 localizações): o 21825 não aparecia lá de todo — quem
  confie no perfil nunca o teria visto. O perfil mistura Espanha (9 das 10
  primeiras entradas eram ES/CAT).
- Taxonomia de procedimentos em PT correcta no universo global: "Ajuste
  Directo / Consulta Prévia", "Concurso Limitado sem Publicação", etc.
- Prazos apresentados com hora e fuso ("16/09/2026 22:59" = 23:59 Lisboa?
  não verificado qual o fuso de referência).
