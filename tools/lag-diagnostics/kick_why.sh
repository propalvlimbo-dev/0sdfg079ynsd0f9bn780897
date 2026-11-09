#!/usr/bin/env bash
# =============================================================================
#  Elytrix KICK WHY — «почему всех выкинуло одновременно»
# =============================================================================
#
#  Разбирает logs/latest.log (и rotated/gz) и отвечает на три вопроса:
#    1. В КАКУЮ МИНУТУ был массовый кик (топ-5 минут по числу отключений)
#    2. ПО КАКОЙ ПРИЧИНЕ (группировка «lost connection: ...» + отдельно LPX,
#       Paper packet-limiter, Netty/ProtocolLib, таймауты)
#    3. ЧТО БЫЛО НЕПОСРЕДСТВЕННО ПЕРЕД ЭТИМ (контекст за 60 сек до пика)
#
#  Только чтение. Ничего не рестартует, не трогает порты :8085/:20559/:24454,
#  пишет только в $DUMPDIR (по умолчанию /root).
#
#  Использование:
#     bash kick_why.sh                       # сам найдёт лог сервера
#     bash kick_why.sh /root/RW_GRIEF/logs/latest.log
#     bash kick_why.sh /root/RW_GRIEF/logs/2026-11-09-1.log.gz
# =============================================================================

set -u

LOG=${1:-}
SERVER_DIR_ARG=${2:-}

OUT_BASE=${DUMPDIR:-/root}
STAMP=$(date +%H%M%S)
OUT="$OUT_BASE/kickwhy-$STAMP.txt"
: > "$OUT" 2>/dev/null || OUT="/tmp/kickwhy-$STAMP.txt"
: > "$OUT" 2>/dev/null || OUT="/dev/null"

have() { command -v "$1" >/dev/null 2>&1; }

# ---------------------------------------------------------------- найти лог
if [ -z "$LOG" ]; then
    for d in "$SERVER_DIR_ARG" /root/RW_GRIEF /root/RW_GRIEF/ /root /home/container .; do
        [ -n "$d" ] || continue
        if [ -f "$d/logs/latest.log" ]; then LOG="$d/logs/latest.log"; break; fi
    done
fi
[ -n "$LOG" ] || { echo "не нашёл logs/latest.log — укажи путь: bash kick_why.sh <путь>"; exit 1; }
[ -f "$LOG" ] || { echo "нет файла: $LOG"; exit 1; }

# распаковка на лету
case "$LOG" in
    *.gz) CAT="gzip -cd" ;;
    *)    CAT="cat"      ;;
esac

TMP=$(mktemp -d 2>/dev/null || echo /tmp/kickwhy.$$)
mkdir -p "$TMP"
$CAT "$LOG" > "$TMP/full.log" 2>/dev/null
TOTAL=$(wc -l < "$TMP/full.log" 2>/dev/null || echo 0)

echo "Elytrix KICK WHY · $LOG · строк: $TOTAL"
echo
echo "==================== 1. МАССОВЫЙ КИК: топ минут по отключениям ===================="
# «lost connection: <причина>» — строка есть у каждого отключения
grep -oE '^\[[0-9]{2}:[0-9]{2}:[0-9]{2}\][^]]*' "$TMP/full.log" 2>/dev/null >/dev/null
# отметки времени Paper/DivineMC: [HH:MM:SS] ... lost connection: X
awk '
  /lost connection/ {
    if (match($0, /[0-9][0-9]:[0-9][0-9]:[0-9][0-9]/)) {
      t = substr($0, RSTART, 5)          # HH:MM
      c[t]++
    }
  }
  END { for (k in c) printf "%6d  %s\n", c[k], k }
' "$TMP/full.log" | sort -rn | head -5

PEAK=$(awk '/lost connection/ { if (match($0, /[0-9][0-9]:[0-9][0-9]:[0-9][0-9]/)) { t=substr($0,RSTART,5); c[t]++ } } END { best=""; n=0; for (k in c) if (c[k]>n) {n=c[k]; best=k} print best }' "$TMP/full.log")

# Пытаемся понять, был ли пик «в момент старта сервера» (тогда это реконнект-шторм, а не кик)
DONE_AT=$(awk '/Done \(/ { if (match($0, /[0-9][0-9]:[0-9][0-9]:[0-9][0-9]/)) { print substr($0, RSTART, 5) ; exit } }' "$TMP/full.log")
if [ -n "${DONE_AT:-}" ]; then
    echo
    echo "    сервер стал готов (Done) в минуту: $DONE_AT"
    if [ "$DONE_AT" = "$PEAK" ]; then
        echo "    >> ВНИМАНИЕ: пик отключений СОВПАДАЕТ с минутой старта сервера!"
        echo "       Скорее всего это НЕ кик, а реконнект-шторм после рестарта (или отключение на входе)."
        echo "       Смотри раздел 6 — там имена игроков и точные формулировки."
    fi
fi

echo
echo "==================== 2. ПРИЧИНЫ ОТКЛЮЧЕНИЙ (по частоте) ===================="
sed -n 's/.*lost connection: //p' "$TMP/full.log" 2>/dev/null \
  | sed -E 's/^(\[CHAT\]|[0-9]+ )?//' \
  | sed -E 's/[0-9]+/N/g' \
  | sort | uniq -c | sort -rn | head -12

echo
echo "==================== 3. КТО КОНКРЕТНО КИКАЛ ===================="
echo "--- 3.1 LPX («You are sending suspicious packets» / kick-alert) ---"
grep -iE 'suspicious packets|LPX >>|lpx kick|You are sending suspicious' "$TMP/full.log" 2>/dev/null | tail -15
echo "    (найдено: $(grep -ciE 'suspicious packets|lpx kick' "$TMP/full.log" 2>/dev/null))"

echo
echo "--- 3.2 Paper packet-limiter («слишком много пакетов») ---"
grep -iE 'exceeded_packet_rate|too many packets|Kicked for spamming|disconnect\.spam' "$TMP/full.log" 2>/dev/null | tail -10
echo "    (найдено: $(grep -ciE 'exceeded_packet_rate|too many packets|Kicked for spamming|disconnect\.spam' "$TMP/full.log" 2>/dev/null))"

echo
echo "--- 3.3 Netty / ProtocolLib / PacketEvents (Internal Exception) ---"
grep -iE 'Internal Exception|io\.netty|DecoderException|EncoderException|packetevents|OutOfDirectMemoryError|Cannot allocate memory' "$TMP/full.log" 2>/dev/null | tail -10
echo "    (найдено: $(grep -ciE 'Internal Exception|io\.netty|DecoderException|EncoderException|packetevents|OutOfDirectMemoryError' "$TMP/full.log" 2>/dev/null))"

echo
echo "--- 3.3b АНТИЧИТЫ (FloriumAC / Grim / Spartan / Vulcan) ---"
grep -iE 'FloriumAC|Florium|GrimAC|\bGrim\b|Spartan|Vulcan' "$TMP/full.log" 2>/dev/null | grep -iE 'transport|exception|kick|disconnect|unavailable|reconnect|timeout|timed out|alert|violation|WARN|ERROR' | tail -15
echo "    (найдено: $(grep -ciE 'FloriumAC|GrimAC|Spartan|Vulcan' "$TMP/full.log" 2>/dev/null))"

echo
echo "--- 3.4 Таймауты (Timed out / keepalive) ---"
grep -iE 'Timed out|timed out|keepalive|keep-alive' "$TMP/full.log" 2>/dev/null | tail -8
echo "    (найдено: $(grep -ciE 'Timed out|keepalive|keep-alive' "$TMP/full.log" 2>/dev/null))"

echo
echo "--- 3.5 Ошибки/исключения (любые, топ) ---"
grep -iE '\[ERROR\]|\[SEVERE\]|Exception|Caused by' "$TMP/full.log" 2>/dev/null \
  | sed -E 's/^\[[0-9]{2}:[0-9]{2}:[0-9]{2}\] //; s/^\[[0-9:.]+T[0-9:.-]+\] //' \
  | sed -E 's/[0-9a-f]{8}-[0-9a-f-]+/UUID/g; s/[0-9]+/N/g' \
  | sort | uniq -c | sort -rn | head -12

echo
echo "==================== 4. ЧТО БЫЛО ПЕРЕД ПИКОМ (минута $PEAK) ===================="
awk -v pk="$PEAK" '
  {
    if (match($0, /[0-9][0-9]:[0-9][0-9]:[0-9][0-9]/)) t = substr($0, RSTART, 5)
    if (t == pk && /Exception|ERROR|SEVERE|WARN|netty|lpx|LPX|kick|Kick|packet|disconnect|Disconnect|Saving|Stopping|Restart/) print
  }
' "$TMP/full.log" | head -30

echo
echo "==================== 5. ВАЖНЫЕ СОБЫТИЯ (рестарт/стоп/сейв/крэш) ===================="
grep -inE 'Stopping server|Restarting|Server thread dump|Crash report|A single server tick|watchdog|Shutting down|Done \(|Enabling .*LPX|LPX.*enabled|Disabling ' "$TMP/full.log" 2>/dev/null | tail -20

echo
echo "=========== 6. КТО ИМЕННО: имена и точные формулировки отключений ==========="
echo "--- 6.1 Все отключения в пиковую минуту ($PEAK) ---"
awk -v pk="$PEAK" '/lost connection/ { if (match($0, /[0-9][0-9]:[0-9][0-9]:[0-9][0-9]/) && substr($0, RSTART, 5) == pk) print }' "$TMP/full.log" | head -40
echo "--- 6.2 Последние 25 отключений (с именами) ---"
grep -E 'lost connection|left the game' "$TMP/full.log" 2>/dev/null | tail -25
echo "--- 6.3 Нестандартные причины кика (всё, кроме «Disconnected»/«Internal Exception») ---"
sed -n 's/.*lost connection: //p' "$TMP/full.log" 2>/dev/null \
  | grep -viE '^Disconnected$|^Internal Exception$|^Internal Exception: io\.netty|^Timed out$' \
  | sed -E 's/[0-9]+/N/g' | sort | uniq -c | sort -rn | head -15

echo
echo "=========== 7. ПЕРВЫЙ ПОЛНЫЙ СТЕКТРЕЙС (кто именно падает) ==========="
# Сначала ищем настоящую ошибку тика/ERROR, и только если её нет — любое исключение.
START=$(grep -n -m1 -E 'Entity threw exception|\[ERROR\]|\[SEVERE\]' "$TMP/full.log" 2>/dev/null | cut -d: -f1)
[ -n "${START:-}" ] || START=$(grep -n -m1 -E 'Exception|Caused by' "$TMP/full.log" 2>/dev/null | cut -d: -f1)
if [ -n "${START:-}" ]; then
    sed -n "${START},$((START+17))p" "$TMP/full.log" 2>/dev/null
else
    echo "    (исключений в логе нет)"
fi

echo
echo "=========== 8. КТО МУТИРУЕТ AI-ЦЕЛИ (WrappedGoal NPE) ==========="
if grep -q 'WrappedGoal' "$TMP/full.log" 2>/dev/null; then
    grep -n -m2 -A 10 'WrappedGoal' "$TMP/full.log" 2>/dev/null
    echo
    echo "    --- кто ещё упоминается рядом с этими NPE (топ плагинов в стектрейсах) ---"
    grep -A 12 'WrappedGoal' "$TMP/full.log" 2>/dev/null \
      | grep -oE 'com\.[a-z0-9_]+\.[a-zA-Z0-9_.]+|plugins/[A-Za-z0-9_.-]+\.jar' \
      | sed -E 's/(com\.[a-z0-9_]+\.[a-zA-Z0-9_]+)\..*/\1/' \
      | sort | uniq -c | sort -rn | head -10
else
    echo "    (WrappedGoal NPE в логе нет)"
fi

echo
echo "==================== ВЫВОД (автоматический) ===================="
LPX=$(grep -ciE 'suspicious packets|lpx kick' "$TMP/full.log" 2>/dev/null)
PL=$(grep -ciE 'exceeded_packet_rate|too many packets|Kicked for spamming' "$TMP/full.log" 2>/dev/null)
NET=$(grep -ciE 'Internal Exception|io\.netty.*Exception|DecoderException|EncoderException|OutOfDirectMemoryError|Cannot allocate memory' "$TMP/full.log" 2>/dev/null)
TO=$(grep -ciE 'Timed out' "$TMP/full.log" 2>/dev/null)
AC=$(grep -ciE 'FloriumAC|GrimAC|Spartan|Vulcan' "$TMP/full.log" 2>/dev/null)
OOM=$(grep -ciE 'OutOfDirectMemoryError|Cannot allocate memory' "$TMP/full.log" 2>/dev/null)

if [ "${LPX:-0}" -gt 0 ]; then
    echo ">> ПОДОЗРЕВАЕТСЯ LPX: найдено $LPX киков «suspicious packets»."
    echo "   Лечение: kick-on-exception: false + checks.netty.*.punish: false в plugins/LPX/config.yml"
fi
if [ "${PL:-0}" -gt 0 ]; then
    echo ">> ПОДОЗРЕВАЕТСЯ Paper packet-limiter: $PL событий."
    echo "   Лечение: поднять packet-limiter.all-packets.max-packet-rate (сейчас 500) в config/paper-global.yml"
fi
if [ "${NET:-0}" -gt 0 ]; then
    echo ">> ПОДОЗРЕВАЕТСЯ Netty/DirectMemory: $NET событий."
    echo "   Лечение: проверить off-heap (live_watch.sh), MaxDirectMemorySize=1536M в start.sh"
fi
if [ "${OOM:-0}" -gt 0 ]; then
    echo ">> КРИТИЧНО: нехватка памяти/off-heap: $OOM."
    echo "   Лечение: MaxDirectMemorySize в start.sh + live_watch.sh (колонка off-heap)."
fi
if [ "${TO:-0}" -gt 0 ]; then
    echo ">> ЕСТЬ ТАЙМАУТЫ: $TO. Это симптом, а не причина — смотреть пункты выше."
fi
if [ -n "${DONE_AT:-}" ] && [ "${DONE_AT:-}" = "${PEAK:-}" ]; then
    echo ">> Пик отключений = минута старта сервера ($PEAK)."
    echo "   Это не похоже на кик: проверь раздел 6 (имена/причины). Если причины «Disconnected»"
    echo "   и имена повторяются — это реконнект-шторм после рестарта. Если разные игроки по одному"
    echo "   разу — смотри античит и авторизацию."
fi
if [ "${AC:-0}" -gt 0 ]; then
    echo ">> В логе светятся античиты ($AC упоминаний)."
    echo "   Отдельное внимание FloriumAC: при недоступности его облака он может отключать игроков пачкой."
    echo "   Проверка: раздел 3.3b. Лечение: fail-open/временное отключение на время проверки."
fi
if [ "${LPX:-0}" -eq 0 ] && [ "${PL:-0}" -eq 0 ] && [ "${NET:-0}" -eq 0 ] && [ "${TO:-0}" -eq 0 ]; then
    echo ">> В логе нет ни LPX, ни packet-limiter, ни Netty, ни таймаутов."
    echo "   Значит кикает НЕ серверный плагин: смотреть пункт 5 (рестарт/стоп) и прокси/сеть."
fi

{
  echo "KICK WHY dump $(date)"
  echo "log: $LOG"
  echo "peak minute: $PEAK"
  echo "lpx=$LPX packetlimiter=$PL netty=$NET timeout=$TO"
} > "$OUT" 2>/dev/null || true

echo
echo "Полный вывод можно переслать в чат. Краткая сводка: $OUT"
[ -d "$TMP" ] && rm -rf "$TMP" 2>/dev/null
exit 0
