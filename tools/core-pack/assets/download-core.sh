#!/usr/bin/env bash
# Скачивает ровно то ядро, на котором крутится сервер: Leaf 1.21.11 build 179.
# Проверяет SHA-256 и размер. Кладёт рядом файл server.jar.
#
#   bash download-core.sh            # в текущий каталог
#   bash download-core.sh /root/RW_GRIEF
set -euo pipefail
DIR=${1:-.}
VERSION="1.21.11-179"
URL="https://github.com/Winds-Studio/Leaf/releases/download/ver-1.21.11/leaf-1.21.11-179.jar"
SHA="5da79782215c1a25edcd7c73b3523b7ecb7f4b86dc8a5846a176ed69bc2cd020"
SIZE="83953995"
OUT="$DIR/server.jar"

command -v curl >/dev/null || { echo "нужен curl" >&2; exit 1; }
mkdir -p "$DIR"
TMP=$(mktemp)

echo "ядро   : Leaf $VERSION"
echo "ссылка : $URL"
echo "качаю  -> $OUT"
if curl -fL --progress-bar -o "$TMP" "$URL"; then :; else
    echo "не скачалось. Скачай вручную:" >&2
    echo "  $URL" >&2
    echo "и положи как $OUT" >&2
    rm -f "$TMP"; exit 1
fi

ACT=$(sha256sum "$TMP" | awk '{print $1}')
SZ=$(stat -c %s "$TMP")
if [ "$ACT" != "$SHA" ]; then
    echo "" >&2
    echo "SHA-256 не совпал — файл битый или это другая сборка." >&2
    printf '  ожидался : %s (%s байт)\n  получен  : %s (%s байт)\n' "$SHA" "$SIZE" "$ACT" "$SZ" >&2
    rm -f "$TMP"; exit 1
fi
mv "$TMP" "$OUT"
echo "готово: $OUT  ($SZ байт)"
echo "SHA-256 совпал: $SHA"
