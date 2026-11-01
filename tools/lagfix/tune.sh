#!/usr/bin/env bash
# tune.sh — пакет оптимизаций ядра одним запуском. Только существующие ключи,
# только значения, у каждого файла .bak. Идемпотентно.
#
# Что и почему (по замерам этого сервера):
#   tickBlockEntities 7.8% + ульи 2.7% + getBlockState/isTicking 7% = 17.5%
#     -> simulation-distance уже 6; ниже добавлено урезание радиуса активации
#        ИИ и склейка дропа, чтобы мобов и предметов тикало меньше.
#   Один тик на 1959 мс при ровном CPU (spark health)
#     -> sync-chunk-writes=false (без fsync на каждую запись чанка) и
#        max-auto-save-chunks-per-tick 24->8 (автосейв не в один тик).
#
# Запуск: bash tune.sh /root/RW_GRIEF
set -u
export LC_ALL=C

DIR=${1:-}
[ -z "$DIR" ] && { echo "использование: bash $0 <папка_сервера>" >&2; exit 1; }
[ -d "$DIR" ] || { echo "нет каталога $DIR" >&2; exit 1; }
DIR=$(readlink -f "$DIR")
[ -d "$DIR/plugins" ] || { echo "нет $DIR/plugins — это точно папка сервера?" >&2; exit 1; }

OK=0; SKIP=0

# setyaml <файл> <путь|через|пайпы> <значение>
setyaml() {
    local f=$1 path=$2 val=$3 tmp
    if [ ! -f "$f" ]; then printf '  --  нет файла %s\n' "${f#$DIR/}"; SKIP=$((SKIP+1)); return; fi
    [ -f "$f.bak" ] || cp "$f" "$f.bak"
    tmp=$(mktemp)
    awk -v path="$path" -v val="$val" '
        BEGIN { n = split(path, P, "|") }
        {
            line = $0
            if (match(line, /^[ ]*[A-Za-z0-9_.-]+:/)) {
                match(line, /^[ ]*/); ind = RLENGTH; key = line
                sub(/^[ ]*/, "", key); sub(/:.*/, "", key)
                while (depth > 0 && sind[depth] >= ind) depth--
                depth++; sind[depth] = ind; skey[depth] = key
                ok = (depth == n)
                if (ok) for (i = 1; i <= n; i++) if (skey[i] != P[i]) { ok = 0; break }
                if (ok) {
                    rest = line; sub(/^[ ]*[A-Za-z0-9_.-]+:[ ]*/, "", rest)
                    tail = ""
                    if (index(rest, "#") > 0) tail = " " substr(rest, index(rest, "#"))
                    printf "%*s%s: %s%s\n", ind, "", key, val, tail
                    changed++; next
                }
            }
            print
        }
        END { if (!changed) exit 3 }
    ' "$f" > "$tmp"
    if [ $? -eq 3 ]; then
        rm -f "$tmp"
        printf '  --  %-42s ключ не найден\n' "$path"
        SKIP=$((SKIP+1)); return
    fi
    mv "$tmp" "$f"
    printf '  ok  %-32s %-42s = %s\n' "$(basename "$f")" "$path" "$val"
    OK=$((OK+1))
}

# setprop <файл> <ключ> <значение>
setprop() {
    local f=$1 k=$2 v=$3
    if [ ! -f "$f" ]; then printf '  --  нет файла %s\n' "${f#$DIR/}"; SKIP=$((SKIP+1)); return; fi
    [ -f "$f.bak" ] || cp "$f" "$f.bak"
    if grep -q "^$k=" "$f"; then
        sed -i "s|^$k=.*|$k=$v|" "$f"
    else
        printf '%s=%s\n' "$k" "$v" >> "$f"
    fi
    printf '  ok  %-32s %-42s = %s\n' "server.properties" "$k" "$v"
    OK=$((OK+1))
}

echo "=== tune: $DIR ==="
echo ""
echo "[1] server.properties"
setprop  "$DIR/server.properties" "sync-chunk-writes"        "false"
setprop  "$DIR/server.properties" "simulation-distance"     "6"

echo ""
echo "[2] config/paper-world-defaults.yml — автосейв не в один тик"
setyaml  "$DIR/config/paper-world-defaults.yml" "chunks|max-auto-save-chunks-per-tick" "8"

echo ""
echo "[3] bukkit.yml — автосейв вдвое реже"
setyaml  "$DIR/bukkit.yml" "ticks-per|autosave" "12000"

echo ""
echo "[4] spigot.yml — радиус активации ИИ, склейка дропа, коллизии"
S="$DIR/spigot.yml"
setyaml "$S" "world-settings|default|entity-activation-range|animals"  "16"
setyaml "$S" "world-settings|default|entity-activation-range|monsters" "24"
setyaml "$S" "world-settings|default|entity-activation-range|misc"     "8"
setyaml "$S" "world-settings|default|entity-activation-range|water"    "8"
setyaml "$S" "world-settings|default|entity-activation-range|villagers" "16"
setyaml "$S" "world-settings|default|merge-radius|item" "3.5"
setyaml "$S" "world-settings|default|merge-radius|exp"  "4.0"
setyaml "$S" "world-settings|default|max-entity-collisions" "2"
setyaml "$S" "world-settings|default|tick-inactive-villagers" "false"
setyaml "$S" "world-settings|default|item-despawn-rate" "4000"

echo ""
echo "=== итог: изменено $OK, пропущено $SKIP ==="
echo "бэкапы: *.bak рядом с каждым изменённым файлом"
echo ""
echo "Дальше: обычный рестарт сервера (server.properties читается только при старте)."
echo "Через 10 минут: bash /tmp/lagfix/jfr30.sh $DIR now 600"
echo "Смотри строку 'из них Server thread'. Было 8833."
