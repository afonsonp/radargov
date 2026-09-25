#!/usr/bin/env bash
# O endereço fixo do painel: https://miragov.pt, por um túnel COM NOME
# da Cloudflare, a correr como serviço do utilizador (radar-tunel.service)
# — arranca com o computador e volta sozinho se cair.
#
#     ./tunel_fixo.sh                      # miragov.pt, miragov.com, radargov.pt
#     ./tunel_fixo.sh miragov.pt outro.pt  # o PRIMEIRO é o endereço público
#
# O túnel responde por TODOS os domínios dados, com e sem www, e o painel
# manda os outros para o primeiro (`ao_endereco_certo()` no radar.py,
# 25/09/2026). Até esse dia o script levava um domínio só e reescrevia a
# configuração com ele — correr com o nome novo apagava o antigo.
#
# É o par permanente do tunel.sh (que dá um endereço aleatório e
# temporário). Precisa de três coisas feitas uma vez, à mão:
#   1. os domínios adicionados à conta da Cloudflare (plano Free);
#   2. os nameservers de cada domínio, no registador, a apontar para os
#      dois que a Cloudflare indicou;
#   3. `cloudflared tunnel login`, que abre uma página da Cloudflare para
#      autorizar ESTE computador — é o Afonso que a aceita no browser.
#
# **O DNS não se faz aqui.** O `cloudflared tunnel route dns` escreve na
# zona do domínio escolhido no login (o `cert.pem` leva um token dessa
# zona só): para outro domínio criava um registo errado dentro dela, do
# género miragov.pt.radargov.pt. Por isso o script confere e diz, para
# cada nome que ainda não responda, o CNAME a criar no painel da
# Cloudflare (DNS › Records, «Proxied»). Correr de novo não faz mal: cada
# passo salta o que já está.
#
# O painel continua a atender só em 127.0.0.1; é o cloudflared que se
# liga a ele daqui. Quem abre o endereço sem sessão vê o site público
# na raiz; o painel está em /entrar. E o config.json leva
# "endereco_publico" com o primeiro domínio, para os links do e-mail.
set -u
cd "$(dirname "$0")"
AQUI="$(pwd)"
if [ $# -gt 0 ]; then DOMINIOS=("$@"); else DOMINIOS=(miragov.pt miragov.com radargov.pt); fi
PUBLICO="${DOMINIOS[0]}"
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
  echo "abre a ligação que ele mostra, escolhe o domínio $PUBLICO e autoriza."
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

# 2. a configuração: todos os domínios, com e sem www. Guarda-se a de
#    antes ao lado, para se poder voltar atrás.
[ -f "$PASTA/config.yml" ] && cp "$PASTA/config.yml" "$PASTA/config.yml.antes"
{
  echo "tunnel: $ID"
  echo "credentials-file: $CREDENCIAIS"
  echo "ingress:"
  for D in "${DOMINIOS[@]}"; do
    for H in "$D" "www.$D"; do
      echo "  - hostname: $H"
      echo "    service: http://127.0.0.1:$PORTA"
    done
  done
  echo "  - service: http_status:404"
} > "$PASTA/config.yml"
"$BIN" tunnel --config "$PASTA/config.yml" ingress validate | sed 's/^/   /' || exit 1

# 3. o serviço do utilizador
mkdir -p "$UNIDADES"
cat > "$UNIDADES/radar-tunel.service" <<FIM
[Unit]
Description=Radar DR: o túnel da Cloudflare para https://$PUBLICO
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
systemctl --user enable radar-tunel.service >/dev/null 2>&1
systemctl --user restart radar-tunel.service || exit 1

# 4. o endereço público nos links do e-mail
source "$AQUI/_python.sh"
"$PY" - <<FIM
import json, os
p = os.path.join("$AQUI", "config.json")
cfg = json.load(open(p, encoding="utf-8"))
if cfg.get("endereco_publico") != "https://$PUBLICO":
    cfg["endereco_publico"] = "https://$PUBLICO"
    json.dump(cfg, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("   config.json: endereco_publico = https://$PUBLICO")
FIM

# 5. o DNS: confere, e diz o que falta criar à mão
FALTA=0
for D in "${DOMINIOS[@]}"; do
  for H in "$D" "www.$D"; do
    if [ -z "$(dig +short "$H" 2>/dev/null)" ]; then
      [ $FALTA -eq 0 ] && echo && echo "Falta o DNS destes, no painel da Cloudflare (DNS › Records, «Proxied»):"
      if [ "$H" = "$D" ]; then NOME_REG="@"; else NOME_REG="www"; fi
      echo "   em $D:  CNAME  $NOME_REG  →  $ID.cfargotunnel.com"
      FALTA=1
    fi
  done
done

echo
echo "Pronto. O painel está em https://$PUBLICO; os outros nomes vão lá ter."
echo "Para ver o serviço:  systemctl --user status radar-tunel.service"
echo "Para o tirar:        systemctl --user disable --now radar-tunel.service"
