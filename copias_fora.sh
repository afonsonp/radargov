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

cat <<'PASSOS'

 Falta o destino. São dois passos, uma vez só.

 1. No browser, cria uma conta gratuita no Backblaze B2
    (https://www.backblaze.com/sign-up/cloud-storage), e lá dentro:
      - um "Bucket" PRIVADO, com um nome à tua escolha (ex.: radargov-copias);
      - uma "Application Key" só para esse bucket.
    Aponta o keyID e a applicationKey: o B2 só mostra a chave uma vez.

 2. Aqui, o rclone vai perguntar. Cria DOIS destinos, por esta ordem:
      a) nome "b2", tipo "b2" (Backblaze B2), com o keyID e a chave;
      b) nome "radargov-fora", tipo "crypt", remote "b2:NOME-DO-BUCKET",
         cifra dos nomes "standard", e uma palavra-passe que o rclone
         pode gerar.

    GUARDA ESSA PALAVRA-PASSE FORA DESTE PC (num gestor de palavras-passe,
    ou em papel). Se este PC se perder e ela com ele, as cópias lá fora
    ficam ilegíveis -- é para isso que servem, e é por isso que ninguém,
    nem o Backblaze, as consegue ler.

 Quando acabares, corre outra vez este guião para confirmar.

PASSOS
read -r -p " Abrir o rclone config agora? [s/N] " sim
if [ "$sim" = "s" ] || [ "$sim" = "S" ]; then
  "$BIN" config
fi
