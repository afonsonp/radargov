#!/usr/bin/env bash
# Dá ao painel um endereço público temporário, para o mostrar a alguém
# que não está neste computador e não vai instalar nada.
#
# Usa o "quick tunnel" da Cloudflare: o cloudflared liga-se daqui para
# fora e a Cloudflare dá um endereço https://qualquer-coisa.trycloudflare.com
# que aponta para o painel em 127.0.0.1:8765. Não abre portas no
# router, não precisa de conta nem de domínio, e acaba quando este
# script acaba (Ctrl+C). O endereço muda de cada vez.
#
# ATENÇÃO: o painel ainda não tem login (etapa 1 do
# docs/historico/ONLINE.md). Quem tiver o endereço vê tudo e pode
# mudar a triagem. O endereço é aleatório e impossível de adivinhar,
# mas só o dês a quem confias, e fecha o túnel quando acabar.
set -u
cd "$(dirname "$0")"

PORTA=8765
BIN=".venv/bin/cloudflared"
ORIGEM="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"

if command -v cloudflared >/dev/null 2>&1; then
  BIN="$(command -v cloudflared)"
elif [ ! -x "$BIN" ]; then
  echo "O cloudflared (o programa que faz o túnel) não está instalado."
  echo "Descarrego-o do GitHub da Cloudflare (cerca de 40 MB) para $BIN?"
  read -r -p "[s/N] " resposta
  case "$resposta" in
    s|S|sim|Sim) ;;
    *) echo "Não descarreguei nada."; exit 1 ;;
  esac
  mkdir -p "$(dirname "$BIN")"
  if ! wget -q --show-progress -O "$BIN" "$ORIGEM"; then
    echo "Não consegui descarregar. Verifica a ligação."
    rm -f "$BIN"
    exit 1
  fi
  chmod +x "$BIN"
fi

if ! (exec 3<>"/dev/tcp/127.0.0.1/$PORTA") 2>/dev/null; then
  echo "O painel não está a atender em 127.0.0.1:$PORTA."
  echo "Arranca-o primeiro (./iniciar.sh, ou systemctl --user start radar-painel.service)."
  exit 1
fi

REGISTO="$(mktemp -t tunel-radar.XXXXXX)"
"$BIN" tunnel --url "http://127.0.0.1:$PORTA" --no-autoupdate >"$REGISTO" 2>&1 &
PID=$!
trap 'kill "$PID" 2>/dev/null; rm -f "$REGISTO"; echo; echo "Túnel fechado."' EXIT INT TERM

echo "A pedir um endereço à Cloudflare..."
ENDERECO=""
for _ in $(seq 1 30); do
  ENDERECO="$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$REGISTO" | head -1)"
  [ -n "$ENDERECO" ] && break
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "O cloudflared saiu antes de dar um endereço:"
    tail -20 "$REGISTO"
    exit 1
  fi
  sleep 1
done

if [ -z "$ENDERECO" ]; then
  echo "Passaram 30 s sem endereço. O que o cloudflared disse:"
  tail -20 "$REGISTO"
  exit 1
fi

echo
echo "  O painel está em:  $ENDERECO"
echo
echo "  Vale enquanto esta janela estiver aberta. Ctrl+C fecha o túnel."
echo "  Sem login: quem tiver o endereço vê e mexe em tudo."
echo
wait "$PID"
