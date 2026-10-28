#!/bin/bash
while true; do
    java \
    -Xms10G \
    -Xmx10G \
    -XX:+UseG1GC \
    -XX:+ParallelRefProcEnabled \
    -XX:MaxGCPauseMillis=100 \
    -XX:+UnlockExperimentalVMOptions \
    -XX:+DisableExplicitGC \
    -XX:+AlwaysPreTouch \
    -XX:G1NewSizePercent=30 \
    -XX:G1MaxNewSizePercent=40 \
    -XX:G1HeapRegionSize=8M \
    -XX:G1ReservePercent=20 \
    -XX:G1HeapWastePercent=5 \
    -XX:G1MixedGCCountTarget=4 \
    -XX:InitiatingHeapOccupancyPercent=15 \
    -XX:G1MixedGCLiveThresholdPercent=90 \
    -XX:G1RSetUpdatingPauseTimePercent=5 \
    -XX:SurvivorRatio=32 \
    -XX:+PerfDisableSharedMem \
    -XX:MaxTenuringThreshold=1 \
    -Dusing.aikars.flags=https://mcflags.emc.gs \
    -Daikars.new.flags=true \
    --add-modules=jdk.incubator.vector \
    -Dfile.encoding=UTF-8 \
    -Dterminal.jline=false \
    -Dterminal.ansi=true \
    -Duser.timezone=Europe/Moscow \
    -Dlog4j2.formatMsgNoLookups=true \
    -jar server.jar nogui

    echo "Сервер перезагрузится через 5 секунд. Нажми Ctrl+C для отмены."
    sleep 5
done
