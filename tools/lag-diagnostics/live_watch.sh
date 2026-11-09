#!/usr/bin/env bash
# =============================================================================
#  Elytrix LIVE WATCH — точечный мониторинг сервера во время стрима/онлайна
# =============================================================================
#
#  Что делает: каждые N секунд печатает ОДИН компактный экран с теми цифрами,
#  которые реально объясняют лаги на этом сервере (и которые spark НЕ видит):
#
#    1. CPU: load, %steal гипервизора, %iowait, %user+%sys  <- троттлинг VDS
#    2. Heap G1: used/max, прирост за интервал
#    3. Паузы GC: максимум за интервал + число пауз >50мс и >100мс
#       (именно -XX:MaxGCPauseMillis=100 в start.sh даёт «ровно 100 мс» фризы)
#    4. RSS процесса и оценка off-heap (RSS - heap)  <- Netty DirectMemory
#    5. Потоки и файловые дескрипторы  <- утечки плагинов
#    6. «Can't keep up!» и ошибки из logs/latest.log за интервал
#    7. Соединения на игровом порту (грубая оценка онлайна)
#    8. Диск: %util/iowait — бэкапы и mysqldump на том же диске
#
#  Только чтение. Ничего не перезапускает, не убивает, не трогает порты
#  :8085 / :20559 / :24454, пишет ТОЛЬКО в $DUMPDIR (по умолчанию /root).
#
#  Использование:
#     bash live_watch.sh            # экран каждые 10 секунд
#     bash live_watch.sh 5          # каждые 5 секунд
#     DUMPDIR=/tmp bash live_watch.sh 15 /root/RW_GRIEF
#
#  Ctrl+C -> итоговая сводка за всё время наблюдения + путь к CSV.
# =============================================================================

set -u

IVAL=${1:-10}
case "$IVAL" in ''|*[!0-9]*) IVAL=10 ;; esac
[ "$IVAL" -lt 3 ] && IVAL=3

SERVER_DIR_ARG=${2:-}

OUT_BASE=${DUMPDIR:-/root}
OUT="$OUT_BASE/elytrix-watch-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT" 2>/dev/null || { echo "нет доступа к $OUT_BASE"; exit 1; }
CSV="$OUT/watch.csv"
EVENTS="$OUT/events.log"
: > "$CSV"
: > "$EVENTS"

have() { command -v "$1" >/dev/null 2>&1; }

# ---------------------------------------------------------------- локация сервера
SERVER_DIR=""
for d in "$SERVER_DIR_ARG" /root/RW_GRIEF /root/RW_GRIEF/ /root /home/container .; do
    [ -n "$d" ] || continue
    if [ -f "$d/server.jar" ] || ls "$d"/leaf*.jar "$d"/divinemc*.jar "$d"/paper*.jar >/dev/null 2>&1; then
        SERVER_DIR=$d; break
    fi
done
[ -n "$SERVER_DIR" ] || SERVER_DIR=$(pwd)

LOGDIR="$SERVER_DIR/logs"
LATEST="$LOGDIR/latest.log"
GCLOG="$LOGDIR/gc.log"

PID=$(pgrep -f "java .*server\.jar" 2>/dev/null | head -1)
[ -n "${PID:-}" ] || PID=$(pgrep -f "java .*[dD]ivinemc.*\.jar" 2>/dev/null | head -1)
[ -n "${PID:-}" ] || PID=$(pgrep -f "java .*leaf.*\.jar" 2>/dev/null | head -1)
[ -n "${PID:-}" ] || PID=$(pgrep -f "java .*paper.*\.jar" 2>/dev/null | head -1)
[ -n "${PID:-}" ] || PID=$(pgrep -x java 2>/dev/null | head -1)

# игровой порт из server.properties (нужен для подсчёта соединений)
PORT=$(sed -n 's/^server-port=\([0-9]*\).*/\1/p' "$SERVER_DIR/server.properties" 2>/dev/null | head -1)
[ -n "${PORT:-}" ] || PORT=25565

# ---------------------------------------------------------------- смещения в логах
off_latest=0; off_gc=0
[ -f "$LATEST" ] && off_latest=$(stat -c %s "$LATEST" 2>/dev/null || echo 0)
[ -f "$GCLOG"  ] && off_gc=$(stat -c %s "$GCLOG" 2>/dev/null || echo 0)

# ---------------------------------------------------------------- CPU снепшот
cpu_snap() {
    # user nice system idle iowait irq softirq steal   (именно в таком порядке в /proc/stat)
    awk '/^cpu /{print $2,$3,$4,$5,$6,$7,$8,$9}' /proc/stat 2>/dev/null
}
read -r u0 n0 s0 i0 w0 ir0 sf0 st0 <<<"$(cpu_snap)"
for v in u0 n0 s0 i0 w0 ir0 sf0 st0; do eval "[ -n \"\${$v:-}\" ] || $v=0"; done
t0=$((u0+n0+s0+i0+w0+ir0+sf0+st0))
read -r la1 la5 la15 _x <<<"$(cut -d' ' -f1-3 /proc/loadavg) 0"

# ---------------------------------------------------------------- дисковый счётчик
disk_snap() {
    local dev=""
    dev=$(awk '$3 ~ /^(sda|vda|nvme0n1|sdb|vdb)$/ {print $3; exit}' /proc/diskstats 2>/dev/null)
    [ -n "$dev" ] || dev=$(awk 'NF>3 {print $3; exit}' /proc/diskstats 2>/dev/null)
    awk -v d="$dev" '$3==d {print $12, $13}' /proc/diskstats 2>/dev/null
}
read -r iot0 ioticks0 <<<"$(disk_snap)"
iot0=${iot0:-0}; ioticks0=${ioticks0:-0}

# ---------------------------------------------------------------- пик values
P_HEAP_MAX=0; P_GC_PAUSE=0; P_RSS=0; P_THREADS=0
SUM_CKU=0; SUM_WARN=0; SUM_ERR=0; SUM_GC_PAUSE=0; N=0
WORST_PAUSE_AT="—"

fmt_mb() { awk -v b="$1" 'BEGIN{printf "%.0f", b/1048576}'; }

# самый жирный кадр: последняя строка GC с "Pause ... Xms"
heap_from_gclog() {
    [ -f "$GCLOG" ] || { echo "0 0"; return; }
    tail -n 400 "$GCLOG" 2>/dev/null \
      | grep -oE '[0-9]+M->[0-9]+M\([0-9]+M\)' | tail -1 \
      | sed -E 's/([0-9]+)M->([0-9]+)M\(([0-9]+)M\)/\2 \3/'
}

new_bytes() {  # file, offset -> печатает новые строки, обновляет off_*
    local f=$1 off=$2 cur
    cur=$(stat -c %s "$f" 2>/dev/null || echo 0)
    if [ "$cur" -lt "$off" ]; then off=0; fi   # лог ротировался
    if [ "$cur" -gt "$off" ]; then tail -c "+$((off+1))" "$f" 2>/dev/null; fi
    echo "$cur"
}

hr() { printf '%s\n' "------------------------------------------------------------------------------"; }

echo "Elytrix LIVE WATCH · сервер: $SERVER_DIR · PID: ${PID:-нет} · интервал ${IVAL}s"
echo "Лог: ${LATEST}   GC: ${GCLOG}"
echo "Дамп пишется в: $OUT"
echo "Ctrl+C — остановить и получить сводку."
sleep 2

trap 'finish=1' INT TERM
finish=0

while [ "$finish" -eq 0 ]; do
    sleep "$IVAL" || break

    TS=$(date '+%H:%M:%S')

    # ---- CPU
    read -r u1 n1 s1 i1 w1 ir1 sf1 st1 <<<"$(cpu_snap)"
    for v in u1 n1 s1 i1 w1 ir1 sf1 st1; do eval "[ -n \"\${$v:-}\" ] || $v=0"; done
    t1=$((u1+n1+s1+i1+w1+ir1+sf1+st1))
    dt=$((t1-t0)); dst=$((st1-st0)); dw=$((w1-w0)); di=$((ir1+sf1-ir0-sf0))
    [ "$dt" -le 0 ] && dt=1
    STEAL=$(awk -v a="$dst" -v b="$dt" 'BEGIN{printf "%.1f", a*100/b}')
    IOW=$(awk   -v a="$dw"  -v b="$dt" 'BEGIN{printf "%.1f", a*100/b}')
    IRQ=$(awk   -v a="$di"  -v b="$dt" 'BEGIN{printf "%.1f", a*100/b}')
    BUSY=$(awk  -v a="$((u1+n1+s1-u0-n0-s0))" -v b="$dt" 'BEGIN{printf "%.0f", a*100/b}')
    u0=$u1; n0=$n1; s0=$s1; i0=$i1; w0=$w1; ir0=$ir1; sf0=$sf1; st0=$st1; t0=$t1

    read -r la1 la5 la15 _x <<<"$(cut -d' ' -f1-3 /proc/loadavg) 0"

    # ---- память ОС
    MEMT=$(awk '/^MemTotal:/{printf "%d", $2/1024}' /proc/meminfo 2>/dev/null)
    MEMA=$(awk '/^MemAvailable:/{printf "%d", $2/1024}' /proc/meminfo 2>/dev/null)
    SWPF=$(awk '/^SwapFree:/{printf "%d", $2/1024}' /proc/meminfo 2>/dev/null)
    SWPT=$(awk '/^SwapTotal:/{printf "%d", $2/1024}' /proc/meminfo 2>/dev/null)
    SWPU=0
    if [ "${SWPT:-0}" -gt 0 ]; then
        SWPU=$(awk -v f="$SWPF" -v t="$SWPT" 'BEGIN{printf "%.0f", (t-f)*100/t}')
    fi

    # ---- процесс java
    RSS=0; THREADS=0; FDS=0; PCPU="—"
    if [ -n "${PID:-}" ] && [ -r "/proc/$PID/statm" ]; then
        RSS=$(awk '{print int($2*4096/1048576)}' "/proc/$PID/statm" 2>/dev/null)
        THREADS=$(awk '/^Threads:/{print $2}' "/proc/$PID/status" 2>/dev/null)
        FDS=$(ls "/proc/$PID/fd" 2>/dev/null | wc -l)
        PCPU=$(ps -o %cpu= -p "$PID" 2>/dev/null | tr -d ' ')
    fi

    # ---- heap
    read -r HU HM <<<"$(heap_from_gclog)"
    HU=${HU:-0}; HM=${HM:-0}
    if have jstat && [ -n "${PID:-}" ]; then
        JS=$(jstat -gc "$PID" 2>/dev/null | awk 'NR==2{printf "%d %d", int(($3+$4+$6+$8)/1024), int(($1+$2+$3+$4+$6+$8)/1024)}')
        [ -n "${JS// /}" ] && { read -r HU HM <<<"$JS"; }
    fi
    HEAP_PCT=0
    [ "${HM:-0}" -gt 0 ] && HEAP_PCT=$(awk -v a="$HU" -v b="$HM" 'BEGIN{printf "%.0f", a*100/b}')
    [ "${HU:-0}" -gt "${P_HEAP_MAX:-0}" ] && P_HEAP_MAX=$HU

    # ---- паузы GC за интервал
    GCMAX=0; GCN50=0; GCN100=0
    if [ -f "$GCLOG" ]; then
        NB=$(new_bytes "$GCLOG" "$off_gc")
        off_gc=$(echo "$NB" | tail -1)
        NEWGC=$(echo "$NB" | head -n -1)
        if [ -n "$NEWGC" ]; then
            PAUSES=$(printf '%s\n' "$NEWGC" | grep -oiE 'pause [a-z ]*[0-9.]+ms|[0-9.]+ms$' \
                     | grep -oE '[0-9]+\.[0-9]+ms$' | tr -d 'ms')
            if [ -n "$PAUSES" ]; then
                GCMAX=$(printf '%s\n' "$PAUSES" | sort -g | tail -1)
                GCN50=$(printf '%s\n' "$PAUSES" | awk '$1>50'  | wc -l)
                GCN100=$(printf '%s\n' "$PAUSES" | awk '$1>100' | wc -l)
                SUM_GC_PAUSE=$(awk -v a="$SUM_GC_PAUSE" -v b="$GCMAX" 'BEGIN{printf "%.1f", a+b}')
            fi
        fi
    fi
    if [ "$(awk -v a="$GCMAX" -v b="$P_GC_PAUSE" 'BEGIN{print (a>b)?1:0}')" = "1" ]; then
        P_GC_PAUSE=$GCMAX; WORST_PAUSE_AT="$TS"
    fi
    [ "${RSS:-0}" -gt "${P_RSS:-0}" ] && P_RSS=$RSS
    [ "${THREADS:-0}" -gt "${P_THREADS:-0}" ] && P_THREADS=$THREADS

    # ---- логи сервера
    CKU=0; ERR=0; WARN=0; LASTERR=""
    if [ -f "$LATEST" ]; then
        NB=$(new_bytes "$LATEST" "$off_latest")
        off_latest=$(echo "$NB" | tail -1)
        NEWL=$(echo "$NB" | head -n -1)
        if [ -n "$NEWL" ]; then
            CKU=$(printf '%s\n'  "$NEWL" | grep -c "Can't keep up")
            ERR=$(printf '%s\n'  "$NEWL" | grep -ciE '\[(ERROR|SEVERE)\]|Exception|Caused by|OutOfMemory')
            WARN=$(printf '%s\n' "$NEWL" | grep -ciE '\[WARN\]')
            LASTERR=$(printf '%s\n' "$NEWL" \
                      | grep -iE '\[ERROR\]|Exception|Caused by' \
                      | sed -E 's/^\[[0-9:.]+\] //; s/^\[[0-9]{2}:[0-9]{2}:[0-9]{2}\] //' \
                      | sort -u | head -2)
            [ -n "$LASTERR" ] && printf '%s\n' "$LASTERR" >>"$EVENTS"
        fi
    fi
    SUM_CKU=$((SUM_CKU+CKU)); SUM_ERR=$((SUM_ERR+ERR)); SUM_WARN=$((SUM_WARN+WARN))
    N=$((N+1))

    # ---- соединения
    CONN=0
    if have ss; then
        CONN=$(ss -tn "sport = :$PORT" 2>/dev/null | grep -c ESTAB)
    elif have netstat; then
        CONN=$(netstat -tn 2>/dev/null | grep -c ":$PORT .*ESTABLISHED")
    fi

    # ---- диск
    read -r iot1 ioticks1 <<<"$(disk_snap)"
    iot1=${iot1:-0}; ioticks1=${ioticks1:-0}
    DUTIL=$(awk -v a="$ioticks1" -v b="$ioticks0" -v iv="$IVAL" 'BEGIN{d=a-b; if(d<0)d=0; u=d/(iv*10); if(u>100)u=100; printf "%.0f", u}')
    iot0=$iot1; ioticks0=$ioticks1
    [ "${DUTIL:-0}" -gt 100 ] && DUTIL=100

    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$TS" "$BUSY" "$STEAL" "$IOW" "$HU" "$HEAP_PCT" "$GCMAX" "$RSS" "$THREADS" "$CKU" "$ERR" "$CONN" >>"$CSV"

    clear
    hr
    printf ' Elytrix LIVE WATCH   %s   тик #%d   интервал %ss        (Ctrl+C — итог)\n' "$TS" "$N" "$IVAL"
    hr
    printf ' CPU     load %s / %s / %s   занято %s%%   STEAL %s%%   iowait %s%%   irq/soft %s%%\n' \
           "${la1:-?}" "${la5:-?}" "${la15:-?}" "${BUSY:-0}" "$STEAL" "$IOW" "$IRQ"
    printf ' ПАМЯТЬ  ОЗУ %s/%s MB свободно   своп %s%% (%s/%s MB)\n' \
           "${MEMA:-0}" "${MEMT:-0}" "$SWPU" "${SWPF:-0}" "${SWPT:-0}"
    printf ' JAVA    heap %s / %s MB (%s%%)   RSS %s MB   off-heap~ %s MB   потоки %s   fd %s   cpu %s%%\n' \
           "${HU:-0}" "${HM:-0}" "$HEAP_PCT" "${RSS:-0}" \
           "$(awk -v r="${RSS:-0}" -v h="${HU:-0}" 'BEGIN{o=r-h; if(o<0)o=0; printf "%d", o}')" \
           "${THREADS:-0}" "${FDS:-0}" "${PCPU:-—}"
    hr
    printf ' GC      макс. пауза за интервал: %s мс   (>50мс: %s   >100мс: %s)   рекорд: %s мс в %s\n' \
           "${GCMAX:-0}" "$GCN50" "$GCN100" "${P_GC_PAUSE:-0}" "$WORST_PAUSE_AT"
    printf ' СЕРВЕР  "Can'"'"'t keep up": %s за интервал (всего %s)   ERROR/искл.: %s (всего %s)   WARN: %s (всего %s)\n' \
           "$CKU" "$SUM_CKU" "$ERR" "$SUM_ERR" "$WARN" "$SUM_WARN"
    printf ' СЕТЬ    соединений на :%s — %s      ДИСК  util %s%%\n' "$PORT" "$CONN" "${DUTIL:-0}"
    hr
    if [ -n "$LASTERR" ]; then
        printf ' ПОСЛЕДНИЕ ОШИБКИ:\n'
        printf '%s\n' "$LASTERR" | cut -c1-150 | sed 's/^/   ! /'
        hr
    fi
    ALERTS=""
    [ "$(awk -v a="$STEAL" 'BEGIN{print (a>5)?1:0}')" = 1 ]  && ALERTS="$ALERTS [CPU STEAL ${STEAL}%]"
    [ "$(awk -v a="$IOW"   'BEGIN{print (a>20)?1:0}')" = 1 ] && ALERTS="$ALERTS [IOWAIT ${IOW}%]"
    [ "$(awk -v a="$DUTIL" 'BEGIN{print (a>60)?1:0}')" = 1 ] && ALERTS="$ALERTS [ДИСК ${DUTIL}%]"
    [ "${GCN100:-0}" -gt 0 ] && ALERTS="$ALERTS [GC>100мс x${GCN100}]"
    if [ "${GCMAX:-0}" != "0" ] && [ "$(awk -v a="$GCMAX" 'BEGIN{print (a>100)?1:0}')" = 1 ]; then
        ALERTS="$ALERTS [ПАУЗА ${GCMAX}мс]"
    fi
    [ "${HEAP_PCT:-0}" -gt 85 ] && ALERTS="$ALERTS [HEAP ${HEAP_PCT}%]"
    OFFH=$(awk -v r="${RSS:-0}" -v h="${HU:-0}" 'BEGIN{o=r-h; if(o<0)o=0; printf "%d", o}')
    [ "${OFFH:-0}" -gt 1500 ] && ALERTS="$ALERTS [OFF-HEAP ${OFFH}MB]"
    [ "${CKU:-0}" -gt 0 ] && ALERTS="$ALERTS [ТИК НЕ ВЛЕЗ x${CKU}]"
    [ "${ERR:-0}" -gt 0 ] && ALERTS="$ALERTS [ERROR x${ERR}]"
    [ "${SWPU:-0}" -gt 5 ] && ALERTS="$ALERTS [СВОП ${SWPU}%]"
    if [ -n "$ALERTS" ]; then
        printf ' \033[1;31mТРЕВОГА:\033[0m%s\n' "$ALERTS"
    else
        printf ' ВСЁ В НОРМЕ  (пороги: steal<=5%%, iowait<=20%%, диск<=60%%, GC<=100мс, heap<=85%%, off-heap<=1500MB)\n'
    fi
done

hr
echo "ИТОГИ НАБЛЮДЕНИЯ (${N} замеров, интервал ${IVAL}s, ~$((N*IVAL)) сек)"
hr
printf '  Пик heap              : %s MB\n' "$P_HEAP_MAX"
printf '  Пик паузы GC          : %s мс  (в %s)  сумма макс-пауз: %s мс\n' "$P_GC_PAUSE" "$WORST_PAUSE_AT" "$SUM_GC_PAUSE"
printf '  Пик RSS               : %s MB\n' "$P_RSS"
printf '  Пик потоков           : %s\n' "$P_THREADS"
printf '  "Can'"'"'t keep up" всего : %s\n' "$SUM_CKU"
printf '  ERROR/исключений всего: %s     WARN всего: %s\n' "$SUM_ERR" "$SUM_WARN"
hr
echo "CSV-таймлайн : $CSV"
echo "Ошибки       : $EVENTS"
echo
echo "Колонки CSV: time cpu% steal% iowait% heapMB heap% gcMaxMs rssMB threads cku err conn"
