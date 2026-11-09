#!/usr/bin/env bash
[ -z "${BASH_VERSION:-}" ] && exec /bin/bash "$0" "$@"
cd "$(dirname "$0")" || exit 1
mkdir -p logs
rm -f .nostart   # флаг «остановить навсегда» сбрасывается при каждом запуске обёртки

# Зажимаем нативные арены glibc (2 вместо 24 арен по 64MB — экономит до 1.5 ГБ RSS)
export MALLOC_ARENA_MAX=2

# Авто-подбор потолка Heap от реальной RAM/cgroup VDS (оставляя запас под DirectMemory, ОС и MySQL)
if [ -z "${HEAP_MAX:-}" ]; then
    MEM_MB=$(awk '/^MemTotal:/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 8192)
    if [ -r /sys/fs/cgroup/memory.max ]; then
        CG=$(cat /sys/fs/cgroup/memory.max 2>/dev/null)
        case "$CG" in ''|max|*[!0-9]*) ;; *)
            [ "$CG" -gt 0 ] && [ "$CG" -lt 1099511627776 ] && MEM_MB=$(( CG / 1048576 )) ;;
        esac
    fi
    if   [ "$MEM_MB" -le 8500 ];  then HEAP_MAX="4608M"
    elif [ "$MEM_MB" -le 10500 ]; then HEAP_MAX="6G"
    elif [ "$MEM_MB" -le 12800 ]; then HEAP_MAX="7G"
    else                               HEAP_MAX="8G"
    fi
fi
HEAP_MIN="${HEAP_MIN:-3G}"
DIRECT_MAX="${DIRECT_MAX:-1536M}"
JAR="${SERVER_JAR:-server.jar}"
[ -f "$JAR" ] || for f in leaf*.jar divinemc*.jar paper*.jar purpur*.jar; do [ -f "$f" ] && JAR="$f" && break; done

# -Dio.netty.maxDirectMemory=0 переводит Netty с NoCleaner на JDK Cleaner под единый лимит MaxDirectMemorySize,
# чтобы буферы PacketEvents (LPX/GrimAC/KnockbackSync)/ViaVersion очищались G1GC и никогда не забивали пул до кика всех игроков.
FLAGS=(
    "-Xms${HEAP_MIN}" "-Xmx${HEAP_MAX}"
    -XX:+UseG1GC
    -XX:+ParallelRefProcEnabled
    -XX:MaxGCPauseMillis=100
    -XX:+UnlockExperimentalVMOptions
    -XX:+ExplicitGCInvokesConcurrent
    -XX:+UseStringDeduplication
    -XX:G1PeriodicGCInterval=30000
    -XX:+G1PeriodicGCInvokesConcurrent
    -XX:+PerfDisableSharedMem
    -XX:MaxMetaspaceSize=640M
    "-XX:MaxDirectMemorySize=${DIRECT_MAX}"
    -Djdk.nio.maxCachedBufferSize=65536
    -Dio.netty.maxDirectMemory=0
    -Dio.netty.eventLoopThreads=4
    -Dio.netty.allocator.useCacheForAllThreads=false
    -Dio.netty.allocator.numDirectArenas=4
    -Dio.netty.allocator.numHeapArenas=4
    -Dio.netty.allocator.maxOrder=7
    -Dio.netty.allocator.smallCacheSize=64
    -Dio.netty.allocator.normalCacheSize=16
    -Dio.netty.allocator.maxCachedBufferCapacity=16384
    -Dio.netty.allocator.cacheTrimIntervalMillis=5000
    -XX:G1NewSizePercent=25
    -XX:G1MaxNewSizePercent=35
    -XX:G1HeapRegionSize=8M
    -XX:G1ReservePercent=15
    -XX:G1HeapWastePercent=5
    -XX:G1MixedGCCountTarget=4
    -XX:InitiatingHeapOccupancyPercent=20
    -XX:G1MixedGCLiveThresholdPercent=85
    -XX:G1RSetUpdatingPauseTimePercent=5
    -XX:SurvivorRatio=32
    -XX:MaxTenuringThreshold=1
    "-Xlog:gc*:file=logs/gc.log:time,uptime,level,tags:filecount=3,filesize=10M"
    -Dfile.encoding=UTF-8
    -Dterminal.jline=false
    -Dterminal.ansi=true
    -Duser.timezone=Europe/Moscow
    -Dlog4j2.formatMsgNoLookups=true
    -Dblib.server.version=1.21.10
)

while true; do
    echo "[Elytrix] Запуск $JAR (Heap: ${HEAP_MIN}..${HEAP_MAX}, Direct: ${DIRECT_MAX}, MALLOC_ARENA_MAX=${MALLOC_ARENA_MAX})..."
    echo "[Elytrix] $(date '+%F %T') START" >> logs/restarts.log
    java "${FLAGS[@]}" -jar "$JAR" nogui
    CODE=$?
    echo "[Elytrix] $(date '+%F %T') exit code $CODE" >> logs/restarts.log
    # Автовозврат: сервер поднимается обратно на ЛЮБОМ коде выхода, в том числе
    # после «чистого» stop. Раньше цикл делал break на коде 0, и после любой штатной
    # остановки сервер оставался лежать выключенным, а игроков просто выкидывало.
    # Чтобы остановить сервер НАВСЕГДА: touch .nostart , затем stop.
    if [ "$CODE" -eq 0 ] && [ -f .nostart ]; then
        rm -f .nostart
        echo "[Elytrix] Штатная остановка (.nostart)." && break
    fi
    echo "[Elytrix] Код выхода $CODE — перезапуск через 5 сек (Ctrl+C для отмены)..."
    sleep 5
done
