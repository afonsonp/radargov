# Tendios Bid — verificação por amostragem (30/08/2026)

Conta do Afonso (Noptis), plano gratuito. Objectivo: confirmar o registado a
29/08 no CONCORRENTES.md e correr o teste de paridade. Confirma-se tudo, e o
defeito da identidade é pior do que estava registado.

## Contadores (consistentes com 29/08)

Painel: 13 495 889 licitações (+773/24h), 9 769 043 avaliações (+5 149/24h),
4 567 464 contratos menores (+14/24h). A 29/08: 13 491 905 — cresceu ~4 000
num dia, coerente com a entrada diária declarada.

## Defeito da identidade, agravado

Pesquisa no Diretório de Órgãos pelo NIF **508080142**: **13 órgãos
encontrados**, todos com o mesmo NIF — 3 grafias da ULS de São José, ~9
variantes do Centro Hospitalar (Universitário) de Lisboa Central (E.P.E. /
E. P. E. / EPE / (CHULC) / (CHLC)), e uma entidade absurda "Centro Hospitalar
Universitário Lisboa Central, E.P.E. + Centro Hospitalar Universitário Lisboa
Central, E.P.E.". A 29/08 tinham-se visto 2; por NIF vêem-se 13. E note-se: a
própria caixa diz "Pesquisar órgãos por nome ou NIF" — o NIF está indexado,
só não é usado como chave de agrupamento.

## Duplicação de fichas, reproduzida num anúncio nosso

Pesquisa "vapor distribuição": **2 leilões** para o mesmo concurso —
"CP/471/2026" (ULS Santo António, **E. P. E.**, limite 16/09 23:59) e
"21825/2026" (ULS Santo António, **EPE**, limite 16/09 00:00). Mesmo título,
mesmo orçamento (122 040 €). É o defeito nº 1 de 29/08, agora observado num
anúncio do próprio teste de paridade. As horas-limite diferem (23:59 vs
00:00) — quem confiar na segunda ficha julga ter um dia a menos.

## Teste de paridade (3 anúncios do radar de 28/08)

| Radar | Tendios | Resultado |
|---|---|---|
| 21811/2026 UMinho | expediente "21811/2026" | Encontrado; publicação 28/08 00:00; ficha com 8 documentos, 3 fontes, CPV, mapa, contactos do organismo (morada, telefone, web) |
| 21825/2026 ULS Sto António | 2 fichas (ver acima) | Encontrado — em duplicado |
| 21809/2026 Sto Tirso E.M. 644 | expediente "21809/2026" | Encontrado, 872 214,2 €, limite 25/09 — **a Tendios tem o anúncio que a Armilar não devolve** |

O expediente usado é a referência do DR — ingestão directa do DR confirmada.

## Outros achados desta passagem

- Encoding partido, visto ao vivo na lista: "Aquisi├¦├żo de servi├¦os",
  "Assistência tãđcnica", "Renovaçãģo", "P.A.N.š169/2026".
- Fugas de castelhano na ficha e no onboarding: "Datos del mapa", "Términos",
  "Educacion, Servicios públicos generales", "Primeros pasos en Tendios",
  "Configúrala una vez y recibe automáticamente las licitaciones...".
- "Filtros inteligentes — O que você está procurando?" com botão
  **Desbloquear** (pago). Abas "Todas" e "Avaliações"/"Estados" com cadeado
  no plano gratuito; a aba utilizável é "Em Dia" (1 711 leilões com a
  "pesquisa personalizada" da conta aplicada).
- A pesquisa de texto demora vários segundos a aplicar-se e a contagem
  antiga fica no ecrã entretanto — parece que não filtrou.
- A ficha da licitação tem cronograma (Publicação → Fim da apresentação →
  Adjudicação), orçamento e valor estimado separados, campos de garantias
  (vazios), e separadores Resumo / Documentos / Fontes / Atividade / Análise.
