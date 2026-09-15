# O prompt para a conversa do design (escrito a 15/09/2026)

Copia daqui para baixo.

---

Vamos tratar do aspecto da aplicação. O CRM ficou feito e está na v1.4.0,
a correr; o que falta é tudo o que é de olhar.

**Lê primeiro**: o `CLAUDE.md`, o `ESTADO.md`, a área «a interface» do
`docs/armadilhas.md` e o `docs/historico/UX-Auditoria.md`. O
`docs/historico/CRM.md` explica a escada, que é o ecrã principal.

## O que eu quero

1. **A aplicação tem aspecto de 2002 e eu quero 2026.** Não sou designer.
   Precisas de me dar um caminho, não uma opinião por ecrã — e depois
   aplicá-lo.

2. **Começa por um `docs/design.md` e uma página de amostra** (uma rota
   tipo `/amostra` que mostre os componentes todos num sítio: botões,
   tabelas, etiquetas, formulários, avisos, o selector da ranhura). Quero
   ver e decidir antes de mexeres em ecrã nenhum.

3. **O lettering.** Escolhe, explica porquê, e mostra-me.

4. **Botões com cores sugestivas da função** — que se veja, sem ler, o
   que confirma, o que cancela e o que é destrutivo.

5. **O calendário tem de mudar.** Não deve continuar como está. Diz-me o
   que lhe está errado antes de o refazeres.

6. **A página de abertura**: indicadores, com o calendário das próximas
   tarefas. Hoje a abertura é a lista dos concursos; eu quero chegar e
   ver o estado do negócio e o que tenho de fazer.

7. **Os descritivos das páginas e das funções saem da app.** O texto que
   explica está no meio do que se usa, e isso é ruído para quem já sabe.

8. **Depois disto, uma passagem ecrã a ecrã.** Não de uma vez: um de cada
   vez, com o antes e o depois, e eu digo se serve.

## Duas coisas para não repetirmos

- **Sobre React**: numa conversa anterior eu disse que sem ele não se
  consegue pôr uma animação enquanto as peças estão a ser lidas. Está
  errado — são umas linhas de CSS e de JS, e o painel já recarrega
  enquanto as peças vêm. O que o React resolveria é estado partilhado
  complicado no cliente, e isso é uma discussão para quando isto for
  multi-empresa. **Não é motivo para o trazer agora.**

- **Corre na minha instalação antes de dizer que está feito.** Foi assim
  que se apanhou, no CRM, o que nenhum teste apanhava: o custo da
  migração, a fealdade dos estados vazios e um número que dizia coisas
  diferentes em dois sítios. A base tem 209 895 anúncios; um ecrã que é
  bonito com três linhas pode ser ilegível com duzentas.

## O que ficou pendente do CRM, e é teu decidir quando

- **O B15 está desligado** (`"triagem_no_git": false`) desde 6/09, por
  uma avaria que já não existe. Enquanto estiver assim, as propostas e os
  contactos não saem deste computador. Pergunta-me.
- **O NIF da casa** em Configurações › Conta está vazio: com ele, o
  cruzamento com o Portal BASE diz «a adjudicação é nossa» em vez de
  perguntar.
- **«O que tenho de fazer hoje, em todos os concursos ao mesmo tempo»** —
  chegou a existir um `/hoje` e saiu; o `agenda()` está no histórico do
  git. Isto cruza-se com o ponto 6.
- **O ramo `claude/separador-curso-leads-54c077`** continua no remoto. Não
  o apagues sem eu dizer.
