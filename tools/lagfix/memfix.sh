#!/usr/bin/env bash
# memfix.sh — ограничивает нативную память JVM, из-за которой кончается RAM.
#
# Замер на этом сервере: RSS 11 740 МБ при heap 7168 МБ -> вне кучи ~4.5 ГБ.
# Netty (ProtocolLib + packetevents + packetevents внутри античита) по умолчанию
# имеет право занять direct-буферов до -Xmx, то есть до 7 ГБ. Плюс metaspace
# без потолка. В сумме 16 ГБ RAM уходят, ядро лезет в своп, и мир встаёт.
#
# Ставит две строки в FLAGS вашего start.sh. Больше ничего не меняет.
#   bash memfix.sh /root/RW_GRIEF [direct_mb] [meta_mb]
set -u
DIR=${1:-}
DIRECT=${2:-1024}
META=${3:-768}
[ -n "$DIR" ] || { echo "использование: bash $0 <папка_сервера> [direct_mb] [meta_mb]" >&2; exit 1; }
SH_FILE=$DIR/start.sh
[ -f "$SH_FILE" ] || { echo "нет $SH_FILE" >&2; exit 1; }
case "$DIRECT" in ''|*[!0-9]*) echo "direct_mb должен быть числом" >&2; exit 1 ;; esac
case "$META" in ''|*[!0-9]*) echo "meta_mb должен быть числом" >&2; exit 1 ;; esac

[ -f "$SH_FILE.bak" ] || cp "$SH_FILE" "$SH_FILE.bak"

CH=0
add_flag() {  # $1=флаг
    local f=$1
    grep -q -- "$f" "$SH_FILE" && { printf '  =   %s уже стоит\n' "$f"; return; }
    # вставляем строкой после -XX:+AlwaysPreTouch (он есть в обоих вариантах скрипта)
    if grep -q -- '-XX:+AlwaysPreTouch' "$SH_FILE"; then
        awk -v ins="$f" '
            { print }
            !done && /-XX:\+AlwaysPreTouch/ { match($0, /^[ ]*/); printf "%s%s\n", substr($0, 1, RLENGTH), ins; done = 1 }
        ' "$SH_FILE" > "$SH_FILE.new" && mv "$SH_FILE.new" "$SH_FILE"
    else
        awk -v ins="$f" '
            { print }
            !done && /-Xmx/ { match($0, /^[ ]*/); printf "%s%s\n", substr($0, 1, RLENGTH), ins; done = 1 }
        ' "$SH_FILE" > "$SH_FILE.new" && mv "$SH_FILE.new" "$SH_FILE"
    fi
    printf '  +   %s\n' "$f"
    CH=$((CH + 1))
}

echo "=== memfix: $SH_FILE ==="
add_flag "-XX:MaxDirectMemorySize=${DIRECT}m"
add_flag "-XX:MaxMetaspaceSize=${META}m"

bash -n "$SH_FILE" || { echo "ФАЙЛ СЛОМАН — возвращаю бэкап" >&2; cp "$SH_FILE.bak" "$SH_FILE"; exit 1; }
echo ""
echo "изменений: $CH"
grep -nE 'MaxDirectMemorySize|MaxMetaspaceSize' "$SH_FILE" | sed 's/^/  /'
echo ""
echo "было: RSS 11 740 МБ при heap 7168 МБ (вне кучи ~4.5 ГБ)"
echo "станет: direct не больше ${DIRECT} МБ, metaspace не больше ${META} МБ"
echo "ожидаемый RSS: ~$(( 7168 + DIRECT + META + 300 )) МБ"
echo ""
echo "дальше: обычный рестарт. потом проверь:"
echo "  bash /tmp/lagfix/jfr30.sh $DIR memsplit"
echo "и свободную память: free -m"
