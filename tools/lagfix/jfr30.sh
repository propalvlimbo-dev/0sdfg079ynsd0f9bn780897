#!/usr/bin/env bash
# jfr30.sh — запись и разбор JFR без перезапуска сервера.
#
#   bash jfr30.sh /root/RW_GRIEF start [секунд]   # по умолчанию 1800
#   bash jfr30.sh /root/RW_GRIEF stop
#   bash jfr30.sh /root/RW_GRIEF report
#
# Почему не через -XX:StartFlightRecording в start.sh:
#   * -XX:+FlightRecorder — пустышка, с JDK 13 deprecated, JFR давно бесплатен;
#   * запись начинается на старте JVM, поэтому duration=200s ловит загрузку
#     мира и плагинов, а не лаг в игре.
# jcmd запускает запись на уже работающем сервере: не нужен рестарт, можно
# включить ровно тогда, когда игроки онлайн.
set -u
export LC_ALL=C

SERVER_DIR=${1:-}
MODE=${2:-start}
DURATION=${3:-1800}
NAME=elytrix
JFR_FILE=$SERVER_DIR/flight.jfr
OUT=$SERVER_DIR/jfr-report.txt

if [ -z "$SERVER_DIR" ]; then
    echo "использование: bash $0 <папка_сервера> [start|stop|report] [секунд]" >&2
    exit 1
fi
cd "$SERVER_DIR" || { echo "нет каталога $SERVER_DIR" >&2; exit 1; }

say() { printf '%s\n' "$*" | tee -a "$OUT"; }

find_pid() {  # только сам java: обёртка start.sh/screen тоже содержит "server.jar"
    if [ -n "${JFR_PID:-}" ]; then printf '%s' "$JFR_PID"; return 0; fi
    local p
    for p in $(pgrep -f 'server\.jar|leaf-|paper-' 2>/dev/null) $(pgrep -x java 2>/dev/null); do
        [ "$(cat "/proc/$p/comm" 2>/dev/null)" = "java" ] && { printf '%s' "$p"; return 0; }
    done
    printf ''
}

tool() {  # ищем jcmd/jfr: сначала рядом с java самого сервера
    local t="$1" d c
    if [ -n "${PID:-}" ] && [ -e "/proc/$PID/exe" ]; then
        d=$(dirname "$(readlink -f "/proc/$PID/exe")")
        [ -x "$d/$t" ] && { printf '%s' "$d/$t"; return 0; }
    fi
    if [ -n "${JAVA_BIN:-}" ] && [ -x "${JAVA_BIN%/*}/$t" ]; then
        printf '%s' "${JAVA_BIN%/*}/$t"; return 0
    fi
    if c=$(command -v "$t" 2>/dev/null); then printf '%s' "$c"; return 0; fi
    if c=$(command -v java 2>/dev/null); then
        d=$(dirname "$(readlink -f "$c")")
        [ -x "$d/$t" ] && { printf '%s' "$d/$t"; return 0; }
    fi
    for c in /usr/lib/jvm/*/bin/"$t" "$SERVER_DIR"/*/bin/"$t" "$SERVER_DIR"/runtime/bin/"$t"; do
        [ -x "$c" ] && { printf '%s' "$c"; return 0; }
    done
    return 1
}

PID=$(find_pid)

case "$MODE" in
start)
    : > "$OUT"
    if [ -z "$PID" ]; then echo "процесс сервера не найден" >&2; exit 1; fi
    JCMD=$(tool jcmd) || { echo "не найден jcmd — нужен полный JDK, не JRE" >&2; exit 1; }
    say "=== JFR start $(date '+%Y-%m-%d %H:%M:%S') ==="
    say "pid: $PID, файл: $JFR_FILE, длительность: ${DURATION}s"
    chk=$("$JCMD" "$PID" JFR.check name="$NAME" 2>&1)
    case "$chk" in
        *"Could not find"*) : ;;
        *) say "останавливаю предыдущую запись '$NAME'"
           "$JCMD" "$PID" JFR.stop name="$NAME" >/dev/null 2>&1 || true ;;
    esac

    out=$("$JCMD" "$PID" JFR.start name="$NAME" settings=profile duration="${DURATION}s" filename="$JFR_FILE" 2>&1)
    printf '%s\n' "$out" | tee -a "$OUT"
    case "$out" in
        *[Aa]lready*|*[Ee]xists*) say ">>> запись с именем $NAME уже идёт — сначала: bash $0 $SERVER_DIR stop" ;;
    esac
    say ""
    say "запись идёт. Через ${DURATION} с она сама остановится и запишет файл."
    say "Можно остановить раньше: bash $0 $SERVER_DIR stop"
    say "Разбор там же: bash $0 $SERVER_DIR report  (нужен jfr из JDK 21+, у Paper он есть)"
    ;;
stop)
    if [ -z "$PID" ]; then echo "процесс сервера не найден" >&2; exit 1; fi
    JCMD=$(tool jcmd) || { echo "не найден jcmd" >&2; exit 1; }
    "$JCMD" "$PID" JFR.stop name="$NAME" filename="$JFR_FILE"
    ls -l "$JFR_FILE" 2>/dev/null || echo "файл не создан — запись не была запущена?"
    ;;
report)
    : > "$OUT"
    if [ ! -f "$JFR_FILE" ]; then echo "нет файла $JFR_FILE" >&2; exit 1; fi
    JFR=$(tool jfr) || { echo "не найден jfr — нужен JDK 21+ (jfr view)" >&2; exit 1; }
    say "=== JFR report $(date '+%Y-%m-%d %H:%M:%S') ==="
    say "файл: $JFR_FILE ($(du -h "$JFR_FILE" | cut -f1))"
    say ""

    say "--- сводка событий ---"
    "$JFR" summary "$JFR_FILE" 2>/dev/null | sed -n '1,24p' | tee -a "$OUT"

    say ""
    say "--- потоков создано (thread-start) ---"
    "$JFR" view --width 100 thread-start "$JFR_FILE" 2>/dev/null | head -20 | tee -a "$OUT"

    say ""
    say "--- кто создаёт потоки ---"
    "$JFR" print --events jdk.ThreadStart "$JFR_FILE" 2>/dev/null | awk '
        /^jdk\.ThreadStart \{/ { inp = 1; nm = ""; fr = ""; gf = 0; next }
        inp && /^  thread = "/ { split($0, a, "\""); nm = a[2] }
        inp && /stackTrace = \[/ { inf = 1; next }
        inf && /^  \]/ { inf = 0; next }
        inf && !gf { fr = $0; sub(/^ +/, "", fr); gf = 1 }
        inp && /^\}$/ {
            inp = 0; total++
            n = nm; sub(/-[0-9]+$/, "", n)
            if (n != "") cnt[n]++
            if (gf) fcnt[fr]++
            next
        }
        END {
            printf "%9d  всего потоков создано за запись\n", total
            for (k in cnt)  printf "%9d  поток: %s\n", cnt[k], k
            for (k in fcnt) printf "%9d  создаёт: %s\n", fcnt[k], k
        }' | sort -k1,1nr | head -14 | tee -a "$OUT"

    say ""
    say "--- пик потоков ---"
    "$JFR" view --width 100 thread-count "$JFR_FILE" 2>/dev/null | head -12 | tee -a "$OUT"

    say ""
    say "--- safepoint (остановки мира) ---"
    "$JFR" print --events jdk.SafepointBegin "$JFR_FILE" 2>/dev/null | awk '
        /^jdk\.SafepointBegin \{/ { inp = 1; d = 0; next }
        inp && /^  duration = / { d = $3 + 0 }
        inp && /^\}$/ { inp = 0; n++; tot += d; if (d > mx) { mx = d; mt = last } next }
        inp && /^  startTime = / { last = $3 }
        END { printf "  %d остановок, суммарно %.2f ms, самая долгая %.2f ms (%s)\n", n, tot, mx, mt }' | tee -a "$OUT"

    say ""
    say "--- самые долгие паузы GC ---"
    "$JFR" print --events jdk.GarbageCollection "$JFR_FILE" 2>/dev/null | awk '
        /^jdk\.GarbageCollection \{/ { inp = 1; d = 0; nm = ""; cs = ""; t = ""; next }
        inp && /^  startTime = / { t = $3 }
        inp && /^  duration = / { d = $3 + 0 }
        inp && /^  name = "/ { split($0, a, "\""); nm = a[2] }
        inp && /^  cause = "/ { split($0, a, "\""); cs = a[2] }
        inp && /^\}$/ {
            inp = 0; n++; tot += d; m++
            dv[m] = d; tv[m] = t; nv[m] = nm; cv[m] = cs
            next
        }
        END {
            printf "  сборок: %d, суммарно %.0f ms, в среднем %.1f ms\n", n, tot, (n ? tot / n : 0)
            for (r = 0; r < 6; r++) {
                bi = 0
                for (i = 1; i <= m; i++) if (dv[i] > 0 && (bi == 0 || dv[i] > dv[bi])) bi = i
                if (!bi) break
                printf "    %s  %7.1f ms  %s (%s)\n", tv[bi], dv[bi], nv[bi], cv[bi]
                dv[bi] = 0
            }
        }' | tee -a "$OUT"

    say ""
    say "--- паузы GC ---"
    "$JFR" view --width 110 gc-pauses "$JFR_FILE" 2>/dev/null | head -22 | tee -a "$OUT"

    say ""
    say "--- горячие методы (сэмплы выполнения) ---"
    "$JFR" view --width 130 hot-methods "$JFR_FILE" 2>/dev/null | head -22 | tee -a "$OUT"

    say ""
    say "--- кто с кем говорит по сети ---"
    "$JFR" view --width 100 socket-reads-by-host "$JFR_FILE" 2>/dev/null | head -12 | tee -a "$OUT"
    "$JFR" view --width 100 socket-writes-by-host "$JFR_FILE" 2>/dev/null | head -12 | tee -a "$OUT"

    say ""
    say "--- аллокация по классам ---"
    "$JFR" view --width 110 allocation-by-class "$JFR_FILE" 2>/dev/null | head -16 | tee -a "$OUT"

    say ""
    say "готово. Пришли $OUT целиком."
    ;;
*)
    echo "неизвестный режим: $MODE" >&2; exit 1 ;;
esac
