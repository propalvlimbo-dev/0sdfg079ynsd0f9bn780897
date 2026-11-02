#!/usr/bin/env bash
# fixall.sh — один заход: убирает ИЗМЕРЕННУЮ причину фризов и ничего лишнего.
#
# Что делает (всё обратимо, каждого шага есть .bak / каталог plugins-off):
#   1. убирает Orebfuscator из plugins/ (и из plugins/update/, если он там лежит)
#   2. выключает в LagFixer модуль anti_chain (там O(n) обход на каждый взрыв)
#   3. переводит GC со ZGC на G1 (ZGC жёг ядра на 3-ядерной машине)
#
# Почему Orebfuscator: его проксимити-воркер раз в 50 мс отправлял пачки
# блок-ченджей из фонового потока, а ProtocolLib возвращал КАЖДЫЙ такой пакет
# в главный поток отдельной задачей (NettyChannelInjector.processOutbound:
# hasMainThreadListener && !isPrimaryThread -> runTask). Замер: 4650 таких
# CraftTask за 2 минуты против 9 у самого тяжёлого из остальных, и 8% главного
# потока в сортировке очереди (CraftScheduler$1.compare / PriorityQueue.siftDown).
#
# Запуск: bash fixall.sh /root/RW_GRIEF
set -u
export LC_ALL=C

DIR=${1:-}
if [ -z "$DIR" ]; then
    echo "использование: bash $0 <папка_сервера>" >&2
    exit 1
fi
[ -d "$DIR" ] || { echo "нет каталога $DIR" >&2; exit 1; }
DIR=$(readlink -f "$DIR")
PL=$DIR/plugins
[ -d "$PL" ] || { echo "нет каталога $PL — это точно папка сервера?" >&2; exit 1; }

say() { printf '%s\n' "$*"; }
CH=0

say "=== fixall: $DIR ==="
say ""

# --- 1. Orebfuscator ---------------------------------------------------------
say "[1/3] Orebfuscator"
OFF=$DIR/plugins-off
mkdir -p "$OFF"
MOVED=0
for f in "$PL"/Orebfuscator*.jar "$PL"/update/Orebfuscator*.jar; do
    [ -e "$f" ] || continue
    mv -f "$f" "$OFF"/ || { say "  НЕ СМОГ убрать $f"; continue; }
    say "  убран: ${f#$DIR/}  ->  plugins-off/$(basename "$f")"
    MOVED=$((MOVED + 1))
done
if [ "$MOVED" -gt 0 ]; then
    CH=$((CH + 1))
else
    say "  jar-а Orebfuscator в plugins/ нет — уже убран или называется иначе"
    say "  вот что есть похожего:"
    ls -1 "$PL" 2>/dev/null | grep -i -E 'oreb|obfus' | sed 's/^/    /' || say "    (ничего)"
fi

# --- 2. LagFixer: anti_chain -------------------------------------------------
say ""
say "[2/3] LagFixer: anti_chain"
LF=$PL/LagFixer/modules/ExplosionOptimizer.yml
if [ -f "$LF" ]; then
    [ -f "$LF.bak" ] || cp "$LF" "$LF.bak"
    SUM0=$(md5sum "$LF" | cut -d' ' -f1)
    awk '
        {
            if (want) {
                # правим только СЛЕДУЮЩУЮ строку после anti_chain:, иначе заденем
                # соседний модуль (в файле десятки enabled: true)
                if ($0 ~ /enabled:[ ]*true/) { sub(/enabled:[ ]*true/, "enabled: false"); n++ }
                want = 0
            } else if ($0 ~ /^[ ]*anti_chain:/) { want = 1 }
            print
        }
        END { if (n) printf "  anti_chain -> enabled: false\n" > "/dev/stderr";
              else   printf "  anti_chain уже выключен\n" > "/dev/stderr" }
    ' "$LF" > "$LF.new" && mv "$LF.new" "$LF"
    [ "$(md5sum "$LF" | cut -d' ' -f1)" = "$SUM0" ] || CH=$((CH + 1))
else
    say "  нет $LF — пропускаю"
fi

# --- 3. GC -------------------------------------------------------------------
say ""
say "[3/3] start.sh: GC"
SH=$DIR/start.sh
if [ -f "$SH" ]; then
    [ -f "$SH.bak" ] || cp "$SH" "$SH.bak"
    OLD=$(grep -m1 '^GC_MODE=' "$SH" || true)
    sed -i 's|^GC_MODE=.*|GC_MODE="${GC_MODE:-g1}"|' "$SH"
    NEW=$(grep -m1 '^GC_MODE=' "$SH" || true)
    say "  было:  ${OLD:-<нет строки>}"
    say "  стало: ${NEW:-<нет строки>}"
    [ "$OLD" = "$NEW" ] || CH=$((CH + 1))
else
    say "  нет $SH — пропускаю (правь GC в своей команде запуска)"
fi

# --- итог --------------------------------------------------------------------
say ""
say "=== проверка ==="
if ls "$PL"/Orebfuscator*.jar >/dev/null 2>&1; then
    say "  ВНИМАНИЕ: Orebfuscator всё ещё в plugins/ — пришли вывод: ls $PL/*.jar | grep -i oreb"
else
    say "  Orebfuscator в plugins/: нет"
fi
say "  бэкапы: plugins-off/, *.bak рядом с изменёнными файлами"
say ""
say "изменений внесено: $CH"
say ""
say "Дальше: обычный запуск сервера. Через 5-10 минут после входа игроков:"
say "  bash /tmp/lagfix/jfr30.sh $DIR now 120"
say "в топе не должно быть CraftScheduler\$1.compare и PriorityQueue.siftDown."
