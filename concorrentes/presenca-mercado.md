# Presença no mercado das empresas concorrentes (30/08/2026)

## No contratos.db local (2020–2026, dump IMPIC)

Consultas usadas (só leitura, agregação por `chave` como manda a regra):

```sql
-- encontrar as chaves
SELECT chave, nome, COUNT(DISTINCT contrato_id) n
FROM contrato_adjudicatario WHERE nome_norm LIKE '%vortal%'
GROUP BY chave ORDER BY n DESC;

-- agregar (exemplo Vortal; ACIN análogo com chave 511135610)
SELECT COUNT(*), SUM(preco_contratual), MIN(data_celebracao), MAX(data_celebracao)
FROM contratos WHERE id IN (SELECT contrato_id FROM contrato_adjudicatario
  WHERE chave IN ('505141019','n:vortal comercio eletronico...','508567416'));
-- + GROUP BY adjudicante_chave / cpv / substr(data_celebracao,1,4)
```

### Vortal (NIF 505141019 + Academia Vortal 508567416)

- **471 contratos, 4 664 233 €**, de 2020-01-06 a 2026-08-17; estável
  (~550–860 k€/ano, 51 contratos já em 2026).
- Quem compra: SPMS (135 k€), ICNF (139 k€), SMAS Sintra, e uma cauda longa
  de **hospitais/ULS** (CHU Algarve, ULS Alto Minho, CHUC, Loures, Médio
  Tejo, Lisboa Norte) e municípios — venda da plataforma electrónica ao
  próprio Estado.
- CPV dominantes: 72000000, 72500000, 72416000 (ASP), 30211300, 72212490.
- Lixo no dump: um adjudicatário chamado
  "https://community.vortal.biz/sts/Login" (NIF 508107997) — 1 contrato.

### ACIN — iCloud Solutions (NIF 511135610, dona da acinGov)

- **622 contratos, 13 952 371 €**, até 2026-08-13; pico em 2025 (6,3 M€),
  puxado pela EMEL (4,07 M€ em 2 contratos).
- Compradores: forte na Madeira (Vice-Presidência do Governo Regional, 19
  contratos; AIM-RAM; Funchal), AT, Município do Porto.

### Tendios, Augusta Labs/SpotGov, VIPA (govgo)

**Zero contratos** como fornecedores do Estado português no corpus (pesquisa
por nome_norm; a Tendios é espanhola, a Augusta Labs e a VIPA simplesmente
não vendem ao Estado por concurso). Nenhum NIF encontrado por nome.

## Referências públicas (pesquisa web, 30/08/2026)

- **Augusta Labs**: fundada em Janeiro de 2024 por Rodrigo Fernandes e João
  Cerejeira (23 anos, ex-Sword Health e ex-McKinsey); seed em Junho de 2026
  com avaliação de **50 M€**; investidores incluem Virgílio Bento (Sword),
  Diogo Mónica (Anchorage), Paulo Rosado (OutSystems), Nuno Sebastião
  (Feedzai); 40+ empregados, crescimento declarado 6×/ano. As notícias
  posicionam-na como "IA para grandes empresas"; o SpotGov é o produto de
  contratação pública (a demo corre em augustalabs.navattic.com). O site
  spotgov.com apresenta João Alves como CEO — discrepância com os fundadores
  noticiados; não resolvida.
  Fontes: [Público](https://www.publico.pt/2026/06/02/enter/noticia/augusta-labs-capta-50-milhoes-melhorar-empresas-ia-2176871),
  [ECO](https://eco.sapo.pt/2026/06/02/augusta-labs-fecha-ronda-com-unicornios-nacionais-e-chuta-avaliacao-para-50-milhoes/),
  [Jornal de Negócios](https://www.jornaldenegocios.pt/empresas/tecnologias/detalhe/augusta-labs-voa-com-fundadores-de-unicornios-portugueses-e-passa-a-valer-50-milhoes).
- **Tendios**: Barcelona, 2023, Xavier Creus e Albert Riera; ~30 empregados;
  ronda de **2 M€** (Easo Ventures, Ona Capital, Archipelago Next, Lukkap);
  clientes nomeados: Telefónica, Acciona, SEAT, ADIF, Ministerio de Defensa,
  Ford. Declaram 5 000+ processos optimizados, −70% tempo de procura.
  Fontes: [Computerworld.es](https://www.computerworld.es/article/3996955/la-startup-espanola-tendios-cierra-una-ronda-de-financiacion-de-dos-millones-de-euros.html),
  [capital-riesgo.es](https://capital-riesgo.es/es/articles/tendios-cierra-ronda-de-2-millones-con-la-participaci-n-de-easo-ventures-ona-capital-archipelago-next-y-su-actual-socio-lukkap-venture-/).
- **VIPA / GovGo**: VIPA fundada em 2019 na Madeira, CEO Pedro Paixão;
  GovGo lançada em Março de 2023; IA integrada em 2024 (comunicados).
  Fontes: [ECO](https://eco.sapo.pt/2023/03/22/govgo-apresenta-todos-os-concursos-publicos-nacionais/),
  [Business-IT](https://business-it.pt/2024/08/13/vipa-pt-integra-inteligencia-artificial-na-sua-plataforma-de-concursos-publicos/).
