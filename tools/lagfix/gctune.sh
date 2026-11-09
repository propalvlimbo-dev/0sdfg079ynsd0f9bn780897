#!/usr/bin/env bash
# gctune.sh — короткие паузы GC вместо редких и длинных.
#
# Замер на этом сервере (301 с, mspt 5, JFR):
#   пауз >= 20 мс: 25, суммарно 912 мс, крупнейшие 118 / 78 / 67 / 53 мс
#   тиков > 50 мс: 18 (0.3%) — они и есть "моргнуло"
#   средний MSPT 5.5 мс, главный поток занят 11% времени
#
# Сервер не перегружен: больно делают только длинные паузы. Молодая генерация
# у Aikar-флагов 30-40% кучи (2.1-2.8 ГБ из 7) — её эвакуация и даёт 50-120 мс.
# Ставим 20-30% и цель паузы 100 мс: пауз больше, зато каждая короткая.
#
#   bash gctune.sh /root/RW_GRIEF            применить
#   bash gctune.sh /root/RW_GRIEF --revert   откатить
set -u
DIR=${1:-}
MODE=${2:-apply}
[ -n "$DIR" ] || { echo "использование: bash $0 <папка_сервера> [--revert]" >&2; exit 1; }
F=$DIR/start.sh
[ -f "$F" ] || { echo "нет $F" >&2; exit 1; }

if [ "$MODE" = "--revert" ]; then
    [ -f "$F.bak" ] || { echo "нет $F.bak" >&2; exit 1; }
    cp "$F.bak" "$F"; echo "откатил из $F.bak"; exit 0
fi

[ -f "$F.bak" ] || cp "$F" "$F.bak"
before=$(md5sum "$F" | cut -d' ' -f1)
CH=0; SKIP=0

# заменить число после ключа: два шага, чтобы sed не спутал \1 с цифрами
num() {  # $1=ключ $2=значение
    local key=$1 val=$2
    if ! grep -qF -- "$key" "$F"; then
        printf '  --  %-26s нет ключа, пропускаю\n' "$key"; SKIP=$((SKIP+1)); return
    fi
    sed -i -E "s|(${key}=)[0-9]+[Mm]?|\1@@X@@|" "$F"
    sed -i "s|@@X@@|${val}|" "$F"
    printf '  ok  %-26s -> %s\n' "$key" "$val"
    CH=$((CH + 1))
}

echo "=== gctune: $F ==="
if grep -qF 'PAUSE_MS="${PAUSE_MS:-' "$F"; then
    sed -i -E 's|PAUSE_MS="\$\{PAUSE_MS:-[0-9]+\}"|PAUSE_MS="${PAUSE_MS:-100}"|' "$F"
    printf '  ok  %-26s -> %s\n' 'PAUSE_MS (по умолчанию)' 100
    CH=$((CH + 1))
else
    printf '  --  %-26s переменной нет\n' 'PAUSE_MS'
fi
num 'MaxGCPauseMillis' 100
num 'G1NewSizePercent' 20
num 'G1MaxNewSizePercent' 30
num 'G1HeapRegionSize' '4M'
num 'G1ReservePercent' 15

if ! bash -n "$F"; then
    echo "ФАЙЛ СЛОМАН — возвращаю бэкап" >&2
    cp "$F.bak" "$F"; exit 1
fi

echo ""
if [ "$(md5sum "$F" | cut -d' ' -f1)" = "$before" ]; then
    echo "ничего не изменилось (уже настроено)"
else
    echo "изменено параметров: $CH, пропущено: $SKIP"
    grep -nE 'PAUSE_MS=|MaxGCPauseMillis|G1NewSizePercent|G1MaxNewSizePercent|G1HeapRegionSize|G1ReservePercent' "$F" | sed 's/^/  /'
fi
echo ""
echo "ожидание: паузы 20-50 мс вместо 50-120 (чаще, но короче)."
echo "после рестарта: bash jfr30.sh $DIR mspt 5  -> блок 'паузы GC'"
echo "откат: bash $0 $DIR --revert"
