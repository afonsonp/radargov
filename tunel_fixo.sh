#!/usr/bin/env bash
# O endereço fixo do painel: https://radargov.pt, por um túnel COM NOME
# da Cloudflare, a correr como serviço do utilizador (radar-tunel.service)
# — arranca com o computador e volta sozinho se cair.
#
# É o par permanente do tunel.sh (que dá um endereço aleatório e
# temporário). Precisa de três coisas feitas uma vez, à mão:
#   1. o domínio adicionado à conta da Cloudflare (plano Free);
#   2. os nameservers do domínio, no registador, a apontar para os dois
#      que a Cloudflare indicou;
#   3. `cloudflared tunnel login`, que abre uma página da Cloudflare para
#      autorizar ESTE computador — é o Afonso que a aceita no browser.
# O resto é este script: cria o túnel "radar" se não existir, aponta o
# DNS do domínio e do www para ele, escreve a configuração e instala o
# serviço. Correr de novo não faz mal: cada passo salta o que já está.
#
# O painel continua a atender só em 127.0.0.1; é o cloudflared que se
# liga a ele daqui. Quem abre o endereço sem sessão vê o site público
# na raiz; o painel está em /entrar. E o
# config.json leva "endereco_publico": "https://radargov.pt", para os
# links do e-mail deixarem de dizer 127.0.0.1.
set -u
cd "$(dirname "$0")"
AQUI="$(pwd)"
DOMINIO="${1:-radargov.pt}"
NOME="radar"
PORTA=8765
BIN="$AQUI/.venv/bin/cloudflared"
command -v cloudflared >/dev/null 2>&1 && BIN="$(command -v cloudflared)"
PASTA="$HOME/.cloudflared"
UNIDADES="$HOME/.config/systemd/user"

if [ ! -x "$BIN" ]; then
  echo "Falta o cloudflared. Corre primeiro ./tunel.sh uma vez (descarrega-o)."
  exit 1
fi

if [ ! -f "$PASTA/cert.pem" ]; then
  echo "Este computador ainda não está autorizado na tua conta da Cloudflare."
  echo "Corre:"
  echo "    $BIN tunnel login"
  echo "abre a ligação que ele mostra, escolhe o domínio $DOMINIO e autoriza."
  echo "Depois volta a correr este script."
  exit 1
fi

# 1. o túnel, se ainda não existe
if ! "$BIN" tunnel list 2>/dev/null | awk '{print $2}' | grep -qx "$NOME"; then
  echo "A criar o túnel «$NOME»..."
  "$BIN" tunnel create "$NOME" || exit 1
fi
ID="$("$BIN" tunnel list 2>/dev/null | awk -v n="$NOME" '$2==n {print $1}' | head -1)"
if [ -z "$ID" ]; then
  echo "Não encontrei o túnel «$NOME» depois de o criar."; exit 1
fi
CREDENCIAIS="$PASTA/$ID.json"
if [ ! -f "$CREDENCIAIS" ]; then
  echo "Faltam as credenciais do túnel em $CREDENCIAIS."
  echo "Apaga o túnel ($BIN tunnel delete $NOME) e volta a correr, para as gerar."
  exit 1
fi

# 2. o DNS: o domínio e o www apontam para o túnel (CNAME; a Cloudflare
#    aplana-o na raiz). Se já apontarem, o comando diz e segue.
for H in "$DOMINIO" "www.$DOMINIO"; do
  "$BIN" tunnel route dns "$NOME" "$H" 2>&1 | grep -v "^$" | sed 's/^/   /'
done

# 3. a configuração
cat > "$PASTA/config.yml" <<FIM
tunnel: $ID
credentials-file: $CREDENCIAIS
ingress:
  - hostname: $DOMINIO
    service: http://127.0.0.1:$PORTA
  - hostname: www.$DOMINIO
    service: http://127.0.0.1:$PORTA
  - service: http_status:404
FIM

# 4. o serviço do utilizador
mkdir -p "$UNIDADES"
cat > "$UNIDADES/radar-tunel.service" <<FIM
[Unit]
Description=Radar DR: o túnel da Cloudflare para https://$DOMINIO
After=network-online.target radar-painel.service
Wants=network-online.target

[Service]
ExecStart=$BIN tunnel --no-autoupdate --config $PASTA/config.yml run
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
FIM
systemctl --user daemon-reload
systemctl --user enable --now radar-tunel.service || exit 1

# 5. o endereço público nos links do e-mail
source "$AQUI/_python.sh"
"$PY" - <<FIM
import json, os
p = os.path.join("$AQUI", "config.json")
cfg = json.load(open(p, encoding="utf-8"))
if cfg.get("endereco_publico") != "https://$DOMINIO":
    cfg["endereco_publico"] = "https://$DOMINIO"
    json.dump(cfg, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("   config.json: endereco_publico = https://$DOMINIO")
FIM

echo
echo "Pronto. O painel está em https://$DOMINIO (e www.$DOMINIO)."
echo "Pode levar uns minutos até o DNS propagar. Para ver o serviço:"
echo "    systemctl --user status radar-tunel.service"
echo "Para o tirar: systemctl --user disable --now radar-tunel.service"
