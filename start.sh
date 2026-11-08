#!/usr/bin/env bash
[ -z "${BASH_VERSION:-}" ] && exec /bin/bash "$0" "$@"
cd "$(dirname "$0")" || exit 1
mkdir -p logs

HEAP_MIN="${HEAP_MIN:-4G}"
HEAP_MAX="${HEAP_MAX:-8G}"
JAR="${SERVER_JAR:-server.jar}"
[ -f "$JAR" ] || for f in leaf*.jar divinemc*.jar paper*.jar purpur*.jar; do [ -f "$f" ] && JAR="$f" && break; done

FLAGS=(
    "-Xms${HEAP_MIN}" "-Xmx${HEAP_MAX}"
    -XX:+UseG1GC
    -XX:+ParallelRefProcEnabled
    -XX:MaxGCPauseMillis=80
    -XX:+UnlockExperimentalVMOptions
    -XX:+ExplicitGCInvokesConcurrent
    -XX:+PerfDisableSharedMem
    -XX:MaxMetaspaceSize=768M
    -XX:MaxDirectMemorySize=2G
    -Djdk.nio.maxCachedBufferSize=262144
    -Dio.netty.eventLoopThreads=4
    -XX:G1NewSizePercent=30
    -XX:G1MaxNewSizePercent=40
    -XX:G1HeapRegionSize=8M
    -XX:G1ReservePercent=15
    -XX:G1HeapWastePercent=5
    -XX:G1MixedGCCountTarget=4
    -XX:InitiatingHeapOccupancyPercent=25
    -XX:G1MixedGCLiveThresholdPercent=90
    -XX:G1RSetUpdatingPauseTimePercent=5
    -XX:SurvivorRatio=32
    -XX:MaxTenuringThreshold=1
    -Dfile.encoding=UTF-8
    -Dterminal.jline=false
    -Dterminal.ansi=true
    -Duser.timezone=Europe/Moscow
    -Dlog4j2.formatMsgNoLookups=true
    -Dblib.server.version=1.21.10
)

while true; do
    echo "[Elytrix] Запуск $JAR (Heap: ${HEAP_MIN}..${HEAP_MAX})..."
    java "${FLAGS[@]}" -jar "$JAR" nogui
    [ "$?" -eq 0 ] && echo "[Elytrix] Штатная остановка (stop)." && break
    echo "[Elytrix] Перезапуск через 5 сек (Ctrl+C для отмены)..."
    sleep 5
done
