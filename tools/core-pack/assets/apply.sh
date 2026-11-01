#!/usr/bin/env bash
# Раскладывает конфиги из пака в каталог сервера. Каждый файл — с бэкапом .bak.
# Повторный запуск ничего не портит: бэкап делается только если его ещё нет.
#
#   bash apply.sh /root/RW_GRIEF
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
DIR=${1:-}
[ -n "$DIR" ] || { echo "использование: bash $0 <папка_сервера>" >&2; exit 1; }
[ -d "$DIR/plugins" ] || { echo "нет $DIR/plugins — это точно папка сервера?" >&2; exit 1; }
DIR=$(readlink -f "$DIR")

n=0
put() {
    local src=$1 dst=$2
    mkdir -p "$(dirname "$DIR/$dst")"
    if [ -f "$DIR/$dst" ]; then
        cmp -s "$src" "$DIR/$dst" && { printf '  =   %s (уже такой)\n' "$dst"; return; }
        [ -f "$DIR/$dst.bak" ] || cp "$DIR/$dst" "$DIR/$dst.bak"
        printf '  <<  %s (старый -> %s.bak)\n' "$dst" "$dst"
    else
        printf '  +   %s (новый)\n' "$dst"
    fi
    install -m 644 "$src" "$DIR/$dst"
    n=$((n + 1))
}

echo "=== apply: $DIR ==="
for f in bukkit.yml spigot.yml pufferfish.yml purpur.yml; do
    [ -f "$HERE/configs/$f" ] && put "$HERE/configs/$f" "$f"
done
for f in paper-global.yml paper-world-defaults.yml leaf-global.yml gale-global.yml gale-world-defaults.yml; do
    [ -f "$HERE/configs/config/$f" ] && put "$HERE/configs/config/$f" "config/$f"
done

# server.properties целиком не копируем: там порты, motd, online-mode — твои.
# Правим только те два ключа, которые относятся к лагам.
SP="$DIR/server.properties"
if [ -f "$SP" ]; then
    [ -f "$SP.bak" ] || cp "$SP" "$SP.bak"
    if grep -q '^sync-chunk-writes=' "$SP"; then
        sed -i 's/^sync-chunk-writes=.*/sync-chunk-writes=false/' "$SP"
    else
        echo 'sync-chunk-writes=false' >> "$SP"
    fi
    printf '  ok  server.properties: sync-chunk-writes=false (остальное не трогал)\n'
    n=$((n + 1))
else
    printf '  --  server.properties не найден, пропускаю\n'
fi

echo ""
echo "изменено файлов: $n"
echo "дальше: обычный рестарт сервера (все эти файлы читаются только при старте)."
