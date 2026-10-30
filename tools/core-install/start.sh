#!/usr/bin/env bash
# ============================================================================
#  Elytrix — запуск сервера (Leaf 1.21.11)
# ----------------------------------------------------------------------------
#  Что делает скрипт:
#   * сам находит Java 21+ (или берёт JAVA_BIN=...);
#   * сам считает heap от реальной памяти машины/контейнера (или HEAP_MB=10G);
#   * пишет GC-лог в logs/gc.log (5 файлов по 20 МБ, со сменой) — без него
#     паузы GC не видно ни в spark, ни где-либо ещё;
#   * НЕ ставит -XX:MaxGCPauseMillis=100: цель паузы 200 мс (Aikar). С 100 мс
#     G1 начинает собирать чаще и мельче, а на 10 ГБ heap всё равно упирается
#     в потолок — это и даёт «ровный MSPT, потом резко ~100».
#   * перезапускает сервер после падения и НЕ перезапускает после штатного
#     `stop` (код выхода 0).
#
#  Переменные окружения (все необязательные):
#    JAVA_BIN=/usr/lib/jvm/java-21-openjdk/bin/java
#    HEAP_MB=10G            — фиксированный heap (иначе 60% RAM, 3..12 ГБ)
#    GC_MODE=zgc            — ZGC (паузы <1 мс, но +10-15% CPU) вместо G1
#    PAUSE_MS=200           — цель паузы G1
#    SERVER_JAR=server.jar  — какой jar запускать
# ============================================================================
set -u

cd "$(dirname "$0")" || exit 1
mkdir -p logs

say() { printf '[start.sh] %s\n' "$*"; }
die() { printf '[start.sh] ОШИБКА: %s\n' "$*" >&2; exit 1; }

# --- Java -------------------------------------------------------------------
java_major() {
    "$1" -version 2>&1 | awk -F'"' '/ version /{print $2; exit}' \
        | awk -F. '{ if ($1 == "1") print $2; else print $1 }'
}

JAVA_BIN="${JAVA_BIN:-}"
if [ -n "$JAVA_BIN" ]; then
    [ -x "$JAVA_BIN" ] || die "JAVA_BIN=$JAVA_BIN не исполняемый"
    JAVA_MAJOR="$(java_major "$JAVA_BIN")"
else
    JAVA_MAJOR=0
    for cand in java /usr/lib/jvm/*/bin/java /opt/java/*/bin/java /usr/java/*/bin/java /opt/*/bin/java; do
        [ -x "$cand" ] || continue
        v="$(java_major "$cand")"
        case "$v" in ''|*[!0-9]*) continue ;; esac
        if [ "$v" -gt "$JAVA_MAJOR" ]; then JAVA_MAJOR="$v"; JAVA_BIN="$cand"; fi
    done
fi

[ -n "${JAVA_BIN:-}" ] || die "Java не найдена. Установи Java 21 (например: apt install -y openjdk-21-jre-headless) или задай JAVA_BIN=/путь/к/java"
case "$JAVA_MAJOR" in ''|*[!0-9]*) die "не удалось определить версию Java ($JAVA_BIN)" ;; esac
[ "$JAVA_MAJOR" -ge 21 ] || die "Leaf 1.21.11 требует Java 21+, найдена Java $JAVA_MAJOR ($JAVA_BIN)"

# --- jar --------------------------------------------------------------------
SERVER_JAR="${SERVER_JAR:-}"
if [ -z "$SERVER_JAR" ]; then
    for cand in server.jar leaf.jar paper.jar purpur.jar; do
        if [ -f "$cand" ]; then SERVER_JAR="$cand"; break; fi
    done
fi
[ -n "$SERVER_JAR" ] || die "в $(pwd) нет server.jar (или leaf.jar/paper.jar)"
[ -f "$SERVER_JAR" ] || die "файл $SERVER_JAR не найден"

# --- память -----------------------------------------------------------------
to_mb() {
    case "$1" in
        *[Gg]) echo $(( ${1%[Gg]} * 1024 )) ;;
        *[Mm]) echo "${1%[Mm]}" ;;
        *)     echo "$1" ;;
    esac
}

mem_total_mb() {
    local limit=""
    if [ -r /sys/fs/cgroup/memory.max ]; then
        limit="$(cat /sys/fs/cgroup/memory.max)"
    elif [ -r /sys/fs/cgroup/memory/memory.limit_in_bytes ]; then
        limit="$(cat /sys/fs/cgroup/memory/memory.limit_in_bytes)"
    fi
    case "$limit" in
        ''|max|*[!0-9]*) ;;
        # больше 1 ТБ — значит лимита нет (cgroup пишет огромное число)
        *) if [ "$limit" -gt 0 ] && [ "$limit" -lt 1099511627776 ]; then
               echo $(( limit / 1024 / 1024 )); return
           fi ;;
    esac
    awk '/^MemTotal:/ {print int($2 / 1024)}' /proc/meminfo
}

if [ -n "${HEAP_MB:-}" ]; then
    HEAP="$(to_mb "$HEAP_MB")"
else
    TOTAL_MB="$(mem_total_mb)"
    case "$TOTAL_MB" in ''|*[!0-9]*) TOTAL_MB=0 ;; esac
    if [ "$TOTAL_MB" -gt 0 ]; then
        HEAP=$(( TOTAL_MB * 3 / 5 ))
        [ "$HEAP" -lt 3072 ] && HEAP=3072
        [ "$HEAP" -gt 12288 ] && HEAP=12288
    else
        HEAP=4096
    fi
fi
[ "$HEAP" -ge 1024 ] || die "heap $HEAP МБ — слишком мало"

# --- флаги JVM ---------------------------------------------------------------
GC_MODE="${GC_MODE:-g1}"
PAUSE_MS="${PAUSE_MS:-200}"
case "$PAUSE_MS" in ''|*[!0-9]*) die "PAUSE_MS должен быть числом" ;; esac

FLAGS=(
    "-Xms${HEAP}M" "-Xmx${HEAP}M"
    -XX:+AlwaysPreTouch
    -XX:+ParallelRefProcEnabled
    -XX:+DisableExplicitGC
    -XX:+PerfDisableSharedMem
    -XX:+ExitOnOutOfMemoryError
    -XX:+UnlockExperimentalVMOptions
    -Dusing.aikars.flags=https://mcflags.emc.gs
    -Daikars.new.flags=true
    -Dfile.encoding=UTF-8
    -Dterminal.jline=false
    -Dterminal.ansi=true
    -Duser.timezone=Europe/Moscow
    -Dlog4j2.formatMsgNoLookups=true
    "-Xlog:gc*:file=logs/gc.log:time,uptime,level,tags:filecount=5,filesize=20M"
)

# модуль incubator.vector есть не в каждой сборке Java: без проверки сервер
# может не стартовать вообще («Module jdk.incubator.vector not found»)
if "$JAVA_BIN" --list-modules 2>/dev/null | grep -q '^jdk\.incubator\.vector'; then
    FLAGS+=(--add-modules=jdk.incubator.vector)
else
    say "модуль jdk.incubator.vector недоступен — запускаю без него (не критично)"
fi

if [ "$GC_MODE" = "zgc" ]; then
    FLAGS+=(-XX:+UseZGC)
    # до JDK 23 генерационный ZGC включается отдельным флагом, в 23+ он уже
    # по умолчанию, а в 24+ флага нет вовсе — поэтому только для 21/22
    if [ "$JAVA_MAJOR" -ge 21 ] && [ "$JAVA_MAJOR" -le 22 ]; then
        FLAGS+=(-XX:+ZGenerational)
    fi
else
    FLAGS+=(
        -XX:+UseG1GC
        "-XX:MaxGCPauseMillis=${PAUSE_MS}"
        -XX:G1NewSizePercent=30
        -XX:G1MaxNewSizePercent=40
        -XX:G1HeapRegionSize=8M
        -XX:G1ReservePercent=20
        -XX:G1HeapWastePercent=5
        -XX:G1MixedGCCountTarget=4
        -XX:InitiatingHeapOccupancyPercent=15
        -XX:G1MixedGCLiveThresholdPercent=90
        -XX:G1RSetUpdatingPauseTimePercent=5
        -XX:SurvivorRatio=32
        -XX:MaxTenuringThreshold=1
    )
fi

ulimit -n 65536 2>/dev/null || true

say "java     : $JAVA_BIN (Java $JAVA_MAJOR)"
say "jar      : $SERVER_JAR"
say "heap     : ${HEAP} МБ"
say "GC       : $GC_MODE$( [ "$GC_MODE" = "g1" ] && printf ' (цель паузы %s мс)' "$PAUSE_MS" )"
say "GC-лог   : logs/gc.log"

# --- цикл запуска ------------------------------------------------------------
RESTARTS=0
while true; do
    START_TS=$SECONDS
    "$JAVA_BIN" "${FLAGS[@]}" -jar "$SERVER_JAR" nogui
    CODE=$?
    UPTIME=$(( SECONDS - START_TS ))

    if [ "$CODE" -eq 0 ]; then
        say "сервер остановлен штатно (stop), автоперезапуск не нужен"
        break
    fi

    # если сервер жил долго — это не «цикл падений», обнуляем счётчик
    [ "$UPTIME" -gt 120 ] && RESTARTS=0
    RESTARTS=$(( RESTARTS + 1 ))

    if [ "$RESTARTS" -ge 5 ]; then
        say "5 падений подряд (код $CODE) — пауза 60 с, чтобы не забить лог"
        sleep 60
        RESTARTS=0
    else
        say "сервер завершился с кодом $CODE, перезапуск через 5 с (Ctrl+C — выйти)"
        sleep 5
    fi
done
