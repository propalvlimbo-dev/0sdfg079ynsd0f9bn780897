#!/usr/bin/env bash
# Elytrix lag collector — «spark ничего не показывает» edition.
#
# Собирает то, чего spark в принципе не видит: паузы G1/GC, троттлинг CPU по
# квоте контейнера, steal time гипервизора, диск, cron/бэкапы, автосейвы.
# Только чтение: ничего не перезапускает, не убивает процессы, не трогает :8085,
# не пишет ничего за пределами каталога /root/lagdump-*.
#
#   bash collect.sh            # 90 секунд наблюдения
#   bash collect.sh 180        # дольше — точнее средние, но дольше ждать
#
# В конце печатает короткий отчёт (его можно целиком скопировать в чат) и путь
# к полному дампу.

set -u
DUR=${1:-90}
case "$DUR" in ''|*[!0-9]*) DUR=90 ;; esac
[ "$DUR" -lt 20 ] && DUR=20

OUT_BASE=${DUMPDIR:-/root}
OUT="$OUT_BASE/lagdump-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT" 2>/dev/null || { echo "нет доступа к $OUT_BASE"; exit 1; }
R="$OUT/report.txt"
: > "$R"
say()  { printf '%s\n' "$*" >>"$R"; }
sect() { say ""; say "== $* =="; }
have() { command -v "$1" >/dev/null 2>&1; }

say "Elytrix lag dump  $(date '+%Y-%m-%d %H:%M:%S %Z')   окно ${DUR}s"

SERVER_DIR=""
for d in /root/RW_GRIEF /root/RW_GRIEF/ /root; do
    [ -f "$d/server.jar" ] && { SERVER_DIR=$d; break; }
done
[ -n "$SERVER_DIR" ] || SERVER_DIR=$(pwd)

# ------------------------------------------------------------------ 1. процесс
sect "1. Java-процесс и флаги"
PID=$(pgrep -f "java .*server\.jar" 2>/dev/null | head -1)
[ -n "${PID:-}" ] || PID=$(pgrep -f "java .*\.jar" 2>/dev/null | head -1)
if [ -n "${PID:-}" ]; then
    say "PID: $PID"
    say "uptime процесса: $(ps -o etimes= -p "$PID" 2>/dev/null | tr -d ' ')s"
    CMD=$(tr '\0' ' ' <"/proc/$PID/cmdline" 2>/dev/null)
    say "cmdline: $CMD"
    say "CPU%: $(ps -o %cpu= -p "$PID" 2>/dev/null | tr -d ' ')   RSS: $(ps -o rss= -p "$PID" 2>/dev/null | awk '{printf "%.1f GB", $1/1048576}')"
else
    say "Java-процесс не найден (сервер не запущен?)"
    PID=""
fi
if [ -n "$PID" ] && have jcmd; then
    { jcmd "$PID" VM.flags; jcmd "$PID" GC.heap_info; } >>"$R" 2>/dev/null || true
fi

# ------------------------------------------------------------------ 2. железо
sect "2. CPU, память, своп"
say "nproc: $(nproc 2>/dev/null)   kernel: $(uname -r)"
grep -m1 "model name" /proc/cpuinfo 2>/dev/null | sed 's/^/cpu: /' >>"$R"
say "loadavg: $(cut -d' ' -f1-3 /proc/loadavg 2>/dev/null)"
awk '/MemTotal|MemAvailable|SwapTotal|SwapFree|Dirty|Writeback/ {printf "%s %d MB\n", $1, $2/1024}' \
    /proc/meminfo 2>/dev/null | sed 's/: /: /' >>"$R"

# ------------------------------------------------------------------ 3. квоты
sect "3. Квоты контейнера (главный невидимый источник спайков)"
for f in /sys/fs/cgroup/cpu.max /sys/fs/cgroup/memory.max /sys/fs/cgroup/cpuset.cpus.effective \
         /sys/fs/cgroup/cpu/cpu.cfs_quota_us /sys/fs/cgroup/cpu/cpu.cfs_period_us; do
    [ -r "$f" ] && say "$(basename "$f"): $(cat "$f" 2>/dev/null)"
done
cpu_stat_file=""
[ -r /sys/fs/cgroup/cpu.stat ] && cpu_stat_file=/sys/fs/cgroup/cpu.stat
[ -z "$cpu_stat_file" ] && [ -r /sys/fs/cgroup/cpu/cpu.stat ] && cpu_stat_file=/sys/fs/cgroup/cpu/cpu.stat
thr_before=0; thr_after=0; thr_us_before=0; thr_us_after=0
if [ -n "$cpu_stat_file" ]; then
    thr_before=$(awk '/^nr_throttled /{print $2}' "$cpu_stat_file" 2>/dev/null)
    thr_us_before=$(awk '/^throttled_(usec|time) /{print $2}' "$cpu_stat_file" 2>/dev/null)
fi

# ------------------------------------------------------------------ 4. замеры
sect "4. Замер ${DUR}s"
snap_gc() { [ -n "$PID" ] && have jstat && jstat -gcutil "$PID" 2>/dev/null | tail -1; }
GC_A=$(snap_gc)
TOP_A=$( { have top && top -b -n1 -o %CPU 2>/dev/null | sed -n '7,17p'; } )
VMSTAT_SAMPLES=$(( DUR / 5 )); [ "$VMSTAT_SAMPLES" -lt 3 ] && VMSTAT_SAMPLES=3
have vmstat && vmstat 5 "$VMSTAT_SAMPLES" >"$OUT/vmstat.txt" 2>&1
have iostat && iostat -x 5 3 >"$OUT/iostat.txt" 2>&1
sleep "$DUR"
GC_B=$(snap_gc)
if [ -n "$cpu_stat_file" ]; then
    thr_after=$(awk '/^nr_throttled /{print $2}' "$cpu_stat_file" 2>/dev/null)
    thr_us_after=$(awk '/^throttled_(usec|time) /{print $2}' "$cpu_stat_file" 2>/dev/null)
fi

# ------------------------------------------------------------------ 5. GC
sect "5. Паузы GC за окно"
if [ -n "${GC_A:-}" ] && [ -n "${GC_B:-}" ]; then
    printf '%s\n%s\n' "$GC_A" "$GC_B" | awk '
        NR==1 { ygc=$7; ygct=$8; fgc=$9; fgct=$10; cgc=$11; cgct=$12; gct=$13 }
        NR==2 {
            n = ($7-ygc) + ($9-fgc) + ($11-cgc)
            t = (($13-gct) * 1000)
            if (n > 0) printf "пауз: %d  суммарно %.0f ms  средняя %.1f ms  (young %d, full %d, concurrent %d)\n", n, t, t/n, $7-ygc, $9-fgc, $11-cgc
            else printf "пауз GC за окно не было (молодых: %d, full: %d)\n", $7-ygc, $9-fgc
        }' >>"$R"
else
    say "jstat недоступен — паузы GC не измерены"
fi
GCLOG=""
for c in "$SERVER_DIR/logs/gc.log" "$SERVER_DIR/gc.log" /root/RW_GRIEF/logs/gc.log; do
    [ -f "$c" ] && { GCLOG=$c; break; }
done
if [ -n "$GCLOG" ]; then
    say "GC-лог: $GCLOG ($(wc -l <"$GCLOG" 2>/dev/null) строк)"
    grep -h "Pause" "$GCLOG" 2>/dev/null | tail -400 \
        | sed -nE 's/.*(Pause [^(]*\([^)]*\)).* ([0-9]+[.,][0-9]+)ms.*/\2 \1/p' \
        | tr ',' '.' | sort -rn | head -5 | sed 's/^/самая долгая пауза: /' >>"$R" || true
else
    say "GC-лога нет — в start.sh не включён -Xlog:gc* (это первое, что надо добавить)"
fi

# ------------------------------------------------------------------ 6. диск
sect "6. Диск и нагрузка"
df -h / /root 2>/dev/null | sed 's/^/df: /' >>"$R" || true
have iostat && [ -f "$OUT/iostat.txt" ] && tail -8 "$OUT/iostat.txt" >>"$R" || true
if [ -f "$OUT/vmstat.txt" ]; then
    say "vmstat (r=очередь, wa=ожидание диска, st=украдено гипервизором):"
    tail -n +3 "$OUT/vmstat.txt" >>"$R" || true
fi
say "top по CPU на момент старта:"
[ -n "${TOP_A:-}" ] && printf '%s\n' "$TOP_A" >>"$R"

# ------------------------------------------------------------------ 7. задачи
sect "7. Запланированные задачи и бэкапы"
{ crontab -l 2>/dev/null | grep -v '^#' | grep -v '^$'; } >>"$R" || true
ls -1 /etc/cron.d /etc/cron.hourly /etc/cron.daily 2>/dev/null | sed 's/^/cron.d: /' >>"$R" || true
have systemctl && systemctl list-timers --all --no-pager 2>/dev/null | head -12 >>"$R" || true
ps -eo pid,etime,%cpu,rss,args 2>/dev/null \
    | grep -Ei "rsync|borg|restic|tar -|tar c|zip -|mysqldump|mariadb-dump|backup" \
    | grep -v grep | head -8 | sed 's/^/процесс: /' >>"$R" || true

# ------------------------------------------------------------------ 8. сервер
sect "8. Сервер и мир"
[ -f "$SERVER_DIR/logs/latest.log" ] && \
    grep -m1 "This server is running" "$SERVER_DIR/logs/latest.log" | sed 's/^/ядро: /' >>"$R" || true
say "размеры миров (MB):"
for w in world world_nether world_the_end; do
    [ -d "$SERVER_DIR/$w" ] && \
        say "  $w: $(du -sm "$SERVER_DIR/$w" 2>/dev/null | cut -f1) MB, region-файлов: $(find "$SERVER_DIR/$w/region" -name '*.mca' 2>/dev/null | wc -l)"
done
[ -f "$SERVER_DIR/server.properties" ] && \
    grep -E "^(view-distance|simulation-distance|max-players|network-compression-threshold|sync-chunk-writes|max-tick-time)" \
        "$SERVER_DIR/server.properties" | sed 's/^/server.properties: /' >>"$R" || true
say "плагинов (jar): $(ls -1 "$SERVER_DIR"/plugins/*.jar 2>/dev/null | wc -l)"
ls -S "$SERVER_DIR"/plugins/*.jar 2>/dev/null | head -10 | xargs -r -n1 basename | sed 's/^/  крупный jar: /' >>"$R" || true
if [ -f "$SERVER_DIR/logs/latest.log" ]; then
    LOG="$SERVER_DIR/logs/latest.log"
    say "в latest.log: 'Can't keep up' — $(grep -c "Can't keep up" "$LOG" 2>/dev/null), 'Overloaded' — $(grep -c -i "overloaded" "$LOG" 2>/dev/null)"
    grep -E "\[(WARN|ERROR)\]" "$LOG" 2>/dev/null | tail -8 | cut -c1-160 | sed 's/^/  /' >>"$R" || true
fi

# ------------------------------------------------------------------ 9. вывод
THROTTLED=$(( ${thr_after:-0} - ${thr_before:-0} ))
THR_MS=$(( (${thr_us_after:-0} - ${thr_us_before:-0}) / 1000 ))
sect "9. Короткий вывод"
if [ "$THROTTLED" -gt 0 ]; then
    say "!! CPU-квота контейнера срабатывала $THROTTLED раз(а), суммарно ${THR_MS} ms за ${DUR}s — ЭТО и есть спайки, spark их не видит."
else
    say "троттлинга CPU по квоте за окно не было (nr_throttled +0)"
fi
say "своп: $(awk '/SwapTotal/{t=$2} /SwapFree/{f=$2} END{if(t>0) printf "%d MB занято из %d MB", (t-f)/1024, t/1024; else print "нет свопа"}' /proc/meminfo 2>/dev/null)"
say "steal time (st) смотрите в vmstat выше: любое устойчивое значение > 0 — это гипервизор VDS"
case "${CMD:-}" in
    *MaxGCPauseMillis=100*) say "!! в start.sh стоит -XX:MaxGCPauseMillis=100: G1 разрешено стопорить сервер до 100 ms — ровно твои спайки «до 100»";;
    *UseZGC*) say "GC: ZGC — паузы не должны быть источником спайков";;
esac
case "${CMD:-}" in
    *UseG1GC*) say "GC: G1 (паузы young обычно 5-30 ms, mixed — до MaxGCPauseMillis)";;
esac

say ""
say "Полный дамп: $OUT"
if have tar; then
    TARBALL="$OUT.tar.gz"
    tar -czf "$TARBALL" -C "$(dirname "$OUT")" "$(basename "$OUT")" 2>/dev/null && say "Архив: $TARBALL"
fi

cat "$R"
