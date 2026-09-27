# O que os cadernos de encargos dizem para decidir ir a jogo

**27/09/2026.** A segunda metade da investigação do Q3, depois do
`SETORES.md`. A pergunta é dele, e com as prioridades dele: **a caução
não conta**; conta (A) **se o objecto cabe na oferta da empresa** — o
que se compra e com que características — e (B) **se a empresa tem
capacidade de entregar**. **Não se construiu nada.** Instantâneo: não se
edita.

## Como se fez

Os 58 cadernos de encargos (CE) em disco, de 52 concursos, lidos por
quatro leitores em paralelo — um por família do `SETORES.md` §2 — com a
mesma grelha (A)/(B), a cláusula e uma citação por achado:

| Família | CE lidos | Nota |
|---|---|---|
| Obras | 11 | de 30 k€ a 10,5 M€ |
| Serviços de TI (CPV 72) | 9 de 10 | o de 1,53 M€ (23804/2026) ficou por ler |
| Bens | 5 | três são TI (licenças, datacenter): a amostra de bens físicos é fraca |
| Outros serviços | 7 | energia, telecomunicações, seguros, eventos, manutenção, médicos |
| Mão-de-obra | 2 | vigilância e limpeza — pouco para generalizar |

A amostra puxa para TI porque as peças só se descarregam dos concursos
que alguém abriu.

## 1. O caderno de encargos sozinho não chega

**Nas obras e nos bens, o corpo do CE é sobretudo um modelo jurídico**
(nos serviços de TI não: a tabela dos perfis está no corpo). Nas obras,
8 dos 11 partilham o mesmo texto-tipo, e dois pares de entidades diferentes
têm trechos iguais palavra por palavra. **O que distingue um concurso
de outro está nos anexos e no Programa do Procedimento:**

- a lista das licenças Cisco (22682/2026) está num `Anexo Técnico` à
  parte, não no CE;
- a especificação do material de mergulho (21275/2026) vem num zip de
  anexo, e a lista dos artigos num terceiro ficheiro;
- a equipa técnica das empreitadas está no CE em 2 de 11 — mas a
  expressão «director de obra» está nas peças das 19 empreitadas em
  disco (`SETORES.md` §3): mora no Programa;
- o prazo concreto de uma obra está no CE em 3 de 11; nos outros, no
  Programa.

**Consequência:** um leitor que responda a (A) e (B) tem de ler o
**conjunto das peças**, não o documento que se chama «caderno de
encargos».

## 2. O ponto cego: o Excel

O radar extrai texto de PDF, DOCX, ZIP (44 com texto) e de parte dos
7z. **Não extrai de Excel**: 24 ficheiros `.xls`/`.xlsx` de 18
concursos estão na base com `texto_estado` «não é PDF» e sem texto. São,
pelos nomes, **exactamente o que (A) e (B) precisam** — mapas de
quantidades (`3_2.2_mapa_de_quantidades.xls`, `MQT.xlsx`,
`4_mapa_quantidades_manutencao_instalacoes.xlsx`), cadastros de
equipamentos a manter (`Anexo I - Cadastro UPS.xlsx`), listas de preços
unitários, relações do património e da frota, matrizes de
conformidade.

Na limpeza (22071/2026), as horas e as frequências — o que permite
estimar o custo laboral — estão numa lista de preços unitários em
Excel; o CE só tem os locais e as janelas de horário.

## 3. O que responde a (A) e (B), por família

### Obras

| | O que é | Onde está |
|---|---|---|
| **(A)** | Obra só civil, ou **obra com equipamento** a fornecer e montar (escadas mecânicas, AVAC, electromecânica de ETAR) — muda quem pode concorrer | Objecto do CE; «fornecimento e montagem» |
| (A) | A categoria do alvará | Anúncio §12 (`SETORES.md` §1) e Programa; no CE quase só «menção do alvará» |
| (A) | Especificações de materiais e projecto | Anexo técnico ou projecto — só um em 11 chegou inteiro em texto |
| **(B)** | Prazo de execução | Programa, ou a cláusula do objecto («com o prazo de execução de 180 dias») |
| (B) | Quantidades | Mapa de quantidades — **sempre Excel** |
| (B) | Equipa técnica, director de obra | Programa (e anexo de compromisso, no Metro) |
| (B) | Condicionantes do local | Cláusulas especiais: «nunca superior a 2 horas e fora dos períodos de ponta» (ETAR de Muge) |

### Bens

| | O que é | Onde está |
|---|---|---|
| **(A)** | A lista de artigos, quantidades, part numbers, SKU; características com S/N | Anexo em **tabela** — é a forma dominante |
| (A) | Marcas com «**ou equivalente**» | Sistemático onde há marca; decide se o catálogo da empresa serve |
| **(B)** | Prazo e local de entrega (um ou vários pontos: 23 CPE na energia) | Corpo do CE, cláusulas fixas |
| (B) | Quantidades **firmes ou estimadas** | «não sendo devida qualquer indemnização (...) pela alteração de quantidades» |
| (B) | Garantia e assistência em horas | Só quantificadas nos bens técnicos: «Suporte 3 anos, 24x7 com tempo de resposta 4 horas» |

### Serviços de TI

| | O que é | Onde está |
|---|---|---|
| **(A)** | **A tecnologia ou o produto nomeado** (APEX, EasyVista, ArcGIS, Dynamics, WordPress, Oracle ODI, Microsoft Entra) | Título, cláusula 1.ª, anexo técnico — é o primeiro filtro |
| (A) | Âmbito funcional, integrações com sistemas existentes | Anexo técnico, em lista |
| **(B)** | **A tabela de perfis**: horas máximas, €/hora, anos de experiência | No corpo do CE, em 8 de 10 — o dado mais estruturado de todos |
| (B) | **Certificações nomeadas por perfil** (Oracle, Esri, Microsoft, EasyVista) | Anexo técnico — barreira dura |
| (B) | SLA e prevenção: «10 minutos para início de análise», 24/7 | Só nos contratos com suporte contínuo |
| (B) | Regime do local; bolsa de horas ou entregáveis por fase | CE; muda o risco e o fluxo de caixa |

**Duas lições desta família:** o **preço base não mede a barreira de
entrada** (70 k€ pede dois elementos sem certificação; 195 k€ pede
certificação Microsoft nomeada e anos rígidos); e **um CPV 72 pode ser
uma compra de bens** — o licenciamento Cisco não tem equipa nem SLA.

### Outros serviços (manutenção, telecomunicações, seguros, eventos, médicos)

O que se compra é um **nível de serviço**. (A): o cadastro dos
equipamentos a manter (**Excel**), as coberturas por ramo nos seguros,
as especificações do evento. (B): **tempos de resposta em horas** (24 h
nos locais críticos, 48 h nos outros), técnicos com qualificação legal
(TIM, gases fluorados; título de especialista nos médicos), bolsas de
horas, datas fixas nos eventos.

### Mão-de-obra (vigilância, limpeza)

(A): os locais — um só ou trinta dispersos — e as tarefas. (B): **a
tabela dos postos × horário × dias**, que dá as horas por mês e, com o
CCT, o custo laboral contra o preço base. Na vigilância estava no CE
(«dias úteis: 1 vigilante, 17:00-08:00»); na limpeza, no Excel. Mais o
alvará da PSP e o título profissional, as equipas mínimas, os
equipamentos a cargo, e o regime dos trabalhadores (o CE da vigilância
exige contrato sem termo).

## 4. O que atravessa todas as famílias

- **As penalidades medem o prazo, não a qualidade**: quase todas são
  «‰ ou % por dia de atraso, até 20 %». Não servem para medir a
  exigência técnica.
- **A caução**, como ele disse, não entrou na leitura.
- **As perguntas de (A) são quase todas «o que é nomeado»**: tecnologia,
  produto, marca, categoria de obra, tipo de equipamento. **As de (B)
  são quase todas números**: horas, perfis, prazos, tempos de resposta,
  quantidades, locais.

## 5. O que isto pede ao produto — para discutir, nada feito

1. **(A) só se responde se a empresa disser o que oferece.** Hoje o
   Mira Gov sabe os CPV do interesse e os documentos do cofre. Não sabe
   as tecnologias, os produtos e as marcas que ela vende, as categorias
   do alvará, nem as certificações das pessoas. Sem isso, a leitura
   extrai o que o concurso pede, mas não o compara com nada.
2. **(B) só se responde se a empresa disser o que tem.** Quantas pessoas
   por perfil, em que regiões, que tempo de resposta consegue dar.
3. **A leitura tem de ler o conjunto das peças**, e por família fazer
   as perguntas da §3 — que é o degrau 2 do `SETORES.md` §6, agora com
   a lista das perguntas.
4. **Ler o Excel.** Sem isso, as quantidades das obras, os cadastros da
   manutenção e as horas da limpeza ficam de fora. É código — a
   decidir.

### O que fica por saber

- O CE de 1,53 M€ (23804/2026) não se leu.
- Bens físicos e mão-de-obra têm amostra fraca. Um par de dias de
  peças descarregadas dessas famílias, antes de desenhar, tirava a
  dúvida.
- Quantas das especificações das obras estão dentro dos zip e quantas
  só citadas — viu-se inteira uma (Peninha).
