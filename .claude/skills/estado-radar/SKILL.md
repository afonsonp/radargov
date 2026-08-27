---
name: estado-radar
description: Mostra o estado do Radar de Concursos — quantos anúncios, quantos por ler, triagem, fases do quadro, validade das capturas, painel e tarefas agendadas. Usar quando o Afonso perguntar como está o radar, se a recolha está a correr, quanto falta ler, ou antes e depois de mexer no radar.py.
---

# Estado do Radar

Corre o guião e mostra a saída ao Afonso, sem a reformatar:

```bash
python ".claude/skills/estado-radar/estado.py"
```

Lê a base em modo só-leitura e não escreve nada. Funciona mesmo com o
`radar.py` a meio de uma alteração que não compila, porque não o importa.

## Como ler o que sai

- **na janela dos N dias, por ler** — o que importa. Fora dessa janela é
  histórico e é lido só quando se abre a ficha, por desenho.
- **erro no relógio** — se aparecer, o agendador está a falhar em
  silêncio há algum tempo. Ver `ultimo_erro_relogio` na tabela `estado`.
- **capturas, N dias** — o token vem da sessão do browser e expira. Se a
  recolha começar a falhar e as capturas tiverem muitos dias, é aí.
- **interessa a 0 com fases preenchidas** — normal depois de "tirar do
  quadro"; confirma-se no histórico do anúncio, que diz quem fez o quê.

## Quando isto não chega

Para perceber *porquê* de algo estar mal, o `ESTADO.md` na pasta do
radar tem o registo técnico e os erros já cometidos. Ler antes de mexer.
