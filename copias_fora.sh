#!/usr/bin/env bash
# As copias fora deste PC (F6, 23/09/2026). Corre-se UMA vez. Descarrega o
# rclone para o .venv, como o tunel.sh faz ao cloudflared, e ajuda a criar
# o destino "radargov-fora": uma pasta cifrada num servico gratuito (o
# Backblaze B2: 10 GB sem cartao). A partir dai a copia diaria manda para
# la, sozinha, o ficheiro de cada empresa e o das contas -- cifrados antes
# de sair daqui. Idempotente: com tudo feito, so mostra o que la esta.
cd "$(dirname "$(readlink -f "$0")")" || exit 1

BIN=".venv/bin/rclone"
DESTINO="radargov-fora"

if [ ! -x "$BIN" ]; then
  echo " A descarregar o rclone..."
  TMP="$(mktemp -d)"
  if ! wget -q --show-progress -O "$TMP/rclone.zip" \
      "https://downloads.rclone.org/rclone-current-linux-amd64.zip"; then
    echo " Não consegui descarregar o rclone. Verifica a ligação."
    rm -rf "$TMP"; exit 1
  fi
  # o _python.sh le-se com source (escolhe o $PY); nao se executa
  source ./_python.sh
  "$PY" -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
    "$TMP/rclone.zip" "$TMP" || { rm -rf "$TMP"; exit 1; }
  mkdir -p .venv/bin
  if ! cp "$TMP"/rclone-*-linux-amd64/rclone "$BIN" || ! chmod 755 "$BIN"; then
    echo " Não consegui instalar o rclone em $BIN."
    rm -rf "$TMP"; exit 1
  fi
  rm -rf "$TMP"
  echo " rclone pronto: $("$BIN" version | head -n 1)"
fi

if "$BIN" listremotes | grep -qx "$DESTINO:"; then
  echo " O destino $DESTINO já está configurado. O que lá está:"
  "$BIN" ls "$DESTINO:copias" 2>/dev/null | tail -n 20
  echo
  echo " Para trazer uma cópia de volta:"
  echo "   $BIN copy $DESTINO:copias/empresa-1-AAAA-MM-DD.db ./restauro/"
  exit 0
fi

# Sem o menu do "rclone config" (23/09/2026: perdia-se nele). Pede so o
# que e preciso e cria os dois destinos: o "b2" com a chave, e o
# "radargov-fora", cifrado, dentro do bucket.
source ./_python.sh
echo
echo " Falta o destino. Precisas do que o Backblaze B2 te deu:"
echo " o keyID, a applicationKey e o nome do bucket (privado)."
echo
if ! "$BIN" listremotes | grep -qx "b2:"; then
  read -r -p " keyID: " CHAVE_ID
  read -r -s -p " applicationKey (não aparece ao escrever): " CHAVE; echo
  if [ -z "$CHAVE_ID" ] || [ -z "$CHAVE" ]; then
    echo " Falta o keyID ou a chave. Nada mudou."; exit 1
  fi
  "$BIN" config create b2 b2 account "$CHAVE_ID" key "$CHAVE" --obscure >/dev/null \
    || { echo " Não consegui criar o destino b2."; exit 1; }
else
  echo " O destino b2 (a chave) já está criado."
fi
read -r -p " Nome do bucket: " BALDE
if [ -z "$BALDE" ]; then echo " Falta o nome do bucket. Nada mudou."; exit 1; fi
if ! "$BIN" lsd "b2:$BALDE" >/dev/null 2>&1; then
  echo " Com esta chave não chego ao bucket «$BALDE»."
  echo " Confere o nome (maiúsculas contam) e se a chave é desse bucket."
  echo " Para refazer a chave: $BIN config delete b2   e corre isto outra vez."
  exit 1
fi
SENHA="$("$PY" -c 'import secrets; print(secrets.token_urlsafe(24))')"
"$BIN" config create "$DESTINO" crypt remote "b2:$BALDE/radargov" \
  filename_encryption standard password "$SENHA" --obscure >/dev/null \
  || { echo " Não consegui criar o destino $DESTINO."; exit 1; }
echo
echo " Pronto. A palavra-passe da cifra das cópias é:"
echo
echo "     $SENHA"
echo
echo " GUARDA-A AGORA FORA DESTE PC (gestor de palavras-passe, ou papel)."
echo " Sem ela as cópias lá fora não se lêem -- nem por ti."
read -r -p " Escreve GUARDEI quando a tiveres guardado: " ok
while [ "$ok" != "GUARDEI" ]; do
  read -r -p " Escreve GUARDEI quando a tiveres guardado: " ok
done
clear
echo " Feito. A primeira verificação de cada dia manda as cópias para lá."
echo " Para ver o que lá está: ./copias_fora.sh"
