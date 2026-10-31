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

make_hi_jfc() {  # копия profile.jfc с частыми сэмплами выполнения
    local jb base out
    jb=$(tool java) || return 1
    base=$(dirname "$(readlink -f "$jb")")/../lib/jfr/profile.jfc
    [ -f "$base" ] || return 1
    out=$SERVER_DIR/hi.jfc
    awk '
        /<event name="jdk.ExecutionSample">/ { ine = 1 }
        ine && /<setting name="period"/ { sub(/>.*</, ">2 ms<"); print; next }
        { print }
        ine && /<\/event>/ { ine = 0 }
    ' "$base" > "$out" || return 1
    printf '%s' "$out"
}

# --- счётчики процессора / cgroup -------------------------------------------
CG2=/sys/fs/cgroup
CG1=/sys/fs/cgroup/cpu
cpu_stat() {  # печатает: nr_throttled throttled_ms usage_ms
    if [ -r "$CG2/cpu.stat" ]; then
        awk '/^usage_usec/ {u=$2} /^nr_throttled/ {t=$2} /^throttled_usec/ {d=$2}
             END { printf "%d %d %d\n", t+0, int((d+0)/1000), int((u+0)/1000) }' "$CG2/cpu.stat"
    elif [ -r "$CG1/cpu.stat" ]; then
        awk '/^nr_throttled/ {t=$2} /^throttled_time/ {d=$2} /^usage_usec/ {u=$2}
             END { printf "%d %d %d\n", t+0, int((d+0)/1000000), int((u+0)/1000) }' "$CG1/cpu.stat"
    else
        printf '0 0 0\n'
    fi
}
CLK=$(getconf CLK_TCK 2>/dev/null || echo 100)
cpu_quota() {
    if [ -r "$CG2/cpu.max" ]; then cat "$CG2/cpu.max"
    elif [ -r "$CG1/cpu.cfs_quota_us" ]; then
        printf '%s %s\n' "$(cat "$CG1/cpu.cfs_quota_us")" "$(cat "$CG1/cpu.cfs_period_us")"
    else echo "нет"; fi
}
psi_cpu() {
    [ -r /proc/pressure/cpu ] || { printf 'n/a\n'; return; }
    awk '/^some/ { for (i = 1; i <= NF; i++) if ($i ~ /^avg10=/) { sub(/avg10=/, "", $i); print $i } }' /proc/pressure/cpu
}
mem_avail_mb() { awk '/^MemAvailable:/ { print int($2 / 1024) }' /proc/meminfo 2>/dev/null; }
swap_used_mb() { awk '/^SwapTotal:/ { t = $2 } /^SwapFree:/ { f = $2 } END { print int((t - f) / 1024) }' /proc/meminfo 2>/dev/null; }
vmstat_get() { awk -v k="$1" '$1 == k { print $2 }' /proc/vmstat 2>/dev/null; }
psi_get() {
    [ -r "/proc/pressure/$1" ] || { printf 'n/a'; return; }
    awk -v c="avg10=" '$1 == "some" || $1 == "full" { for (i = 1; i <= NF; i++) if (index($i, c) == 1) { v = $i; sub(c, "", v); print v; exit } }' "/proc/pressure/$1"
}
jvm_majflt() { awk '{ print $12 }' "/proc/$1/stat" 2>/dev/null; }
jvm_ticks() {  # utime+stime процесса в тиках
    awk '{ print $14 + $15 }' "/proc/$1/stat" 2>/dev/null
}


PID=$(find_pid)

analyze_window() {  # $1 файл, $2 lo, $3 hi — печатает события и сэмплы окна
    WFILE=$1; LO=$2; HI=$3
    "$JFR" print --events jdk.ThreadPark,jdk.JavaMonitorEnter,jdk.JavaMonitorWait,jdk.SocketRead,jdk.SocketWrite,jdk.FileRead,jdk.FileWrite,jdk.GarbageCollection,jdk.ZAllocationStall,jdk.ExecutionSample,jdk.NativeMethodSample \
        --stack-depth 6 "$WFILE" 2>/dev/null | awk -v lo="$LO" -v hi="$HI" '
        /^jdk\.[A-Za-z0-9_.]+ \{/ { ev = $1; inp = 1; st = ""; th = ""; dur = 0; nfr = 0; inf = 0; fr[1] = ""; fr[2] = ""; fr[3] = ""; next }
        inp && /^  startTime = / { st = $3 }
        inp && /^  duration = / { dur = $3 + 0 }
        inp && /^  eventThread = "/ { split($0, a, "\""); th = a[2] }
        inp && /^  sampledThread = "/ { if (th == "") { split($0, a, "\""); th = a[2] } }
        inp && /stackTrace = \[/ { inf = 1; next }
        inf && /^  \]/ { inf = 0; next }
        inf && nfr < 3 { nfr++; fr[nfr] = $0; sub(/^ +/, "", fr[nfr]) }
        inp && /^\}$/ {
            inp = 0
            split(st, b, ":"); sec = b[1] * 3600 + b[2] * 60 + b[3]
            if (st != "" && sec >= lo && sec <= hi) {
                key = ev "  [" th "]  " fr[1]
                if (fr[2] != "") key = key " <- " fr[2]
                cnt[key]++
                if (dur >= 15) { nl++; ed[nl] = dur; et[nl] = st; ek[nl] = key }
            }
            next
        }
        END {
            m = 0
            for (k in cnt) ks[++m] = k
            for (i = 2; i <= m; i++) {
                x = ks[i]; j = i - 1
                while (j > 0 && cnt[ks[j]] < cnt[x]) { ks[j + 1] = ks[j]; j-- }
                ks[j + 1] = x
            }
            print "  по количеству событий:"
            for (i = 1; i <= m && i <= 14; i++) printf "  %5d  %s\n", cnt[ks[i]], ks[i]
            if (nl > 0) {
                print ""
                print "  самые долгие события в окне:"
                for (r = 0; r < 10; r++) {
                    bi = 0
                    for (i = 1; i <= nl; i++) if (!used[i] && (bi == 0 || ed[bi] < ed[i])) bi = i
                    if (!bi) break
                    used[bi] = 1
                    printf "  %8.1f ms  %s  %s\n", ed[bi], et[bi], ek[bi]
                }
            }
        }' | tee -a "$OUT"
    say ""
    say "--- чем был занят Server thread в окне (сэмплы) ---"
    "$JFR" print --events jdk.ExecutionSample,jdk.NativeMethodSample --stack-depth 8 "$WFILE" 2>/dev/null | awk -v lo="$LO" -v hi="$HI" '
        /^jdk\.[A-Za-z0-9_.]+ \{/ { ev = $1; inp = 1; st = ""; th = ""; nfr = 0; inf = 0; fr[1] = ""; fr[2] = ""; fr[3] = ""; next }
        inp && /^  startTime = / { st = $3 }
        inp && /^  sampledThread = "/ { split($0, a, "\""); th = a[2] }
        inp && /^  eventThread = "/ { if (th == "") { split($0, a, "\""); th = a[2] } }
        inp && /stackTrace = \[/ { inf = 1; next }
        inf && /^  \]/ { inf = 0; next }
        inf && nfr < 3 { nfr++; fr[nfr] = $0; sub(/^ +/, "", fr[nfr]); sub(/ line:.*/, "", fr[nfr]) }
        inp && /^\}$/ {
            inp = 0
            split(st, b, ":"); sec = b[1] * 3600 + b[2] * 60 + b[3]
            if (st != "" && sec >= lo && sec <= hi && th ~ /^Server thread/) {
                k = fr[1]
                if (fr[2] != "") k = k " <- " fr[2]
                if (fr[3] != "") k = k " <- " fr[3]
                cnt[k]++
            }
            next
        }
        END {
            m = 0; for (k in cnt) ks[++m] = k
            for (i = 2; i <= m; i++) { x = ks[i]; j = i - 1; while (j > 0 && cnt[ks[j]] < cnt[x]) { ks[j+1] = ks[j]; j-- } ks[j+1] = x }
            if (m == 0) print "  сэмплов по Server thread в окне нет (JFR сэмплит редко)"
            for (i = 1; i <= m && i <= 10; i++) printf "  %4d  %s\n", cnt[ks[i]], ks[i]
        }' | tee -a "$OUT"
}

case "$MODE" in
dump)  # снимок идущей записи без остановки
    if [ -z "$PID" ]; then echo "процесс сервера не найден" >&2; exit 1; fi
    JCMD=$(tool jcmd) || { echo "не найден jcmd" >&2; exit 1; }
    PART=$SERVER_DIR/part.jfr
    "$JCMD" "$PID" JFR.dump name="$NAME" filename="$PART"
    ls -l "$PART" 2>/dev/null
    echo
    echo "дальше: bash $0 $SERVER_DIR window HH:MM:SS 10 $PART"
    ;;
ticks)  # история медленных тиков из лога: время, длительность, интервал
    N=${3:-30}
    LOGF=${4:-logs/latest.log}
    [ -f "$LOGF" ] || { echo "нет $LOGF" >&2; exit 1; }
    grep -a 'lasted' "$LOGF" | tail -n "$N" | awk '
        {
            t = substr($0, 2, 8)
            ms = ""
            if (match($0, /lasted [0-9]+[.,]?[0-9]* ms/)) { ms = substr($0, RSTART + 7, RLENGTH - 10); gsub(/,/, ".", ms) }
            split(t, a, ":"); sec = a[1] * 3600 + a[2] * 60 + a[3]
            d = (prev == "" ? 0 : sec - prev)
            printf "  %s  %8.1f ms   %s\n", t, ms, (prev == "" ? "" : "+" d " с")
            prev = sec
        }'
    ;;
cpu)  # раз в секунду: CPU, троттлинг, память, swap, page faults
    SECS=${3:-1800}
    OUTCPU=$SERVER_DIR/cpu.log
    if [ -z "$PID" ]; then echo "процесс сервера не найден" >&2; exit 1; fi
    {
        echo "# $(date '+%Y-%m-%d %H:%M:%S') ядер: $(nproc), quota: $(cpu_quota), pid: $PID"
        echo "# thr=периоды троттлинга throttled_ms=мс троттлинга cpu_ms=CPU мс ядра jvm=%CPU процесса"
        echo "# avail=свободно МБ swap=занято swap МБ swpin/swpout=страниц в/из swap за секунду"
        echo "# majflt=крупных page fault за секунду psi_mem=давление памяти avg10"
    } > "$OUTCPU"
    echo "пишу $OUTCPU каждую секунду, ${SECS} с. Проверить: tail -3 $OUTCPU   Остановить: Ctrl+C"
    t_end=$(( $(date +%s) + SECS ))
    prev_t=""; prev_u=""; prev_j=""; prev_i=""; prev_o=""; prev_f=""
    while [ "$(date +%s)" -lt "$t_end" ]; do
        read -r th th_ms u <<< "$(cpu_stat)"
        j=$(jvm_ticks "$PID"); f=$(jvm_majflt "$PID")
        i=$(vmstat_get pswpin); o=$(vmstat_get pswpout)
        if [ -z "$prev_t" ]; then
            line="$(date '+%H:%M:%S') thr=$th thr_ms=$th_ms cpu_ms=0 jvm=0 avail=$(mem_avail_mb) swap=$(swap_used_mb) swpin=0 swpout=0 majflt=0 psi_mem=$(psi_get memory)"
        else
            dj=$(( j - prev_j )); du=$(( u - prev_u ))
            di=$(( i - prev_i )); do_=$(( o - prev_o )); df=$(( f - prev_f ))
            [ "$du" -lt 0 ] && du=0
            line="$(date '+%H:%M:%S') thr=$th thr_ms=$th_ms cpu_ms=$du jvm=$(( dj * 100 / CLK )) avail=$(mem_avail_mb) swap=$(swap_used_mb) swpin=$di swpout=$do_ majflt=$df psi_mem=$(psi_get memory)"
        fi
        printf '%s\n' "$line" >> "$OUTCPU"
        prev_t=$th; prev_u=$u; prev_j=$j; prev_i=$i; prev_o=$o; prev_f=$f
        sleep 1
    done
    echo "готово: $OUTCPU"
    ;;
cpu-report)  # троттлинг и память против лагов
    OUTCPU=$SERVER_DIR/cpu.log
    [ -f "$OUTCPU" ] || { echo "нет $OUTCPU - сначала: bash $0 $SERVER_DIR cpu 1800" >&2; exit 1; }
    : > "$OUT"
    say "=== CPU/mem report $(date '+%Y-%m-%d %H:%M:%S') ==="
    head -4 "$OUTCPU" | sed 's/^/  /' | tee -a "$OUT"
    say ""
    awk '
        /^#/ { next }
        {
            n++
            for (i = 2; i <= NF; i++) {
                split($i, kv, "="); k = kv[1]; v = kv[2] + 0
                if (k == "thr") th = v
                if (k == "thr_ms") thm = v
                if (k == "jvm") { jv = v; if (v > maxjv) maxjv = v }
                if (k == "avail") { av = v; if (minav == "" || v < minav) { minav = v; minav_t = $1 } }
                if (k == "swap") { sw = v; if (v > maxsw) maxsw = v }
                if (k == "swpin") spi = v
                if (k == "swpout") spo = v
                if (k == "majflt") mf = v
                if (k == "psi_mem") { pm = v; if (v > maxpm) maxpm = v }
            }
            split($1, t, ":"); secs[n] = t[1] * 3600 + t[2] * 60 + t[3] + 0; txt[n] = $1
            thi[n] = th; thi_ms[n] = thm; avi[n] = av; spi_a[n] = spi; spo_a[n] = spo; mf_a[n] = mf
            tot_spi += spi; tot_spo += spo; tot_mf += mf
        }
        END {
            printf "  секунд наблюдения: %d\n", n
            printf "  троттлинг CPU: %d периодов, %.1f с (пик CPU процесса %d%% ядра)\n", thi[n], thi_ms[n] / 1000, maxjv
            printf "  свободная память: минимум %d МБ (%s)\n", minav, minav_t
            printf "  swap занято: максимум %d МБ; страниц в swap %d, из swap %d\n", maxsw, tot_spo, tot_spi
            printf "  крупных page fault за всё время: %d; пик давления памяти PSI avg10: %.2f\n", tot_mf, maxpm
            print ""
            if (maxsw > 0 || tot_spi > 0) print "  >>> память: swap реально использовался - это причина зависаний, не догадка"
            if (tot_spi == 0 && maxsw > 0) print "  >>> swap заполнен, но обратно не читался: страницы просто выгружены, хуже не стало"
            if (maxsw == 0 && tot_spi == 0) print "  >>> swap не использовался"
            if (thi[n] == 0) print "  >>> троттлинга CPU-квоты не было"
            save_n = n
        }' "$OUTCPU" | tee -a "$OUT"

    if [ -f "$SERVER_DIR/lag-events.log" ]; then
        say ""
        say "--- что было в момент каждого лага ---"
        awk '
            FNR == NR { if ($0 ~ /^\[/) { lt = substr($0, 2, 8); split(lt, a, ":"); lag[++nl] = a[1] * 3600 + a[2] * 60 + a[3]; lagtxt[nl] = lt } next }
            /^#/ { next }
            {
                m++
                split($1, t, ":"); mt[m] = t[1] * 3600 + t[2] * 60 + t[3] + 0
                for (i = 2; i <= NF; i++) {
                    split($i, kv, "="); k = kv[1]; v = kv[2] + 0
                    if (k == "majflt") mf[m] = v
                    if (k == "swpin") spi[m] = v
                    if (k == "avail") av[m] = v
                    if (k == "jvm") jv[m] = v
                }
            }
            END {
                if (nl == 0) { print "  lag-events.log пуст"; exit }
                for (k = 1; k <= nl; k++) {
                    sMF = 0; sSP = 0; minA = -1; maxJ = 0; cnt = 0
                    for (i = 1; i <= m; i++) {
                        if (mt[i] >= lag[k] - 2 && mt[i] <= lag[k] + 10) {
                            cnt++; sMF += mf[i]; sSP += spi[i]
                            if (minA < 0 || av[i] < minA) minA = av[i]
                            if (jv[i] > maxJ) maxJ = jv[i]
                        }
                    }
                    if (cnt == 0) { printf "  %s  нет данных (запись не шла)\n", lagtxt[k]; continue }
                    printf "  %s  page faults %4d, чтений из swap %3d, свободно %4d МБ, CPU %3d%%", lagtxt[k], sMF, sSP, minA, maxJ
                    if (sMF > 500 || sSP > 0) print "  << МЕМОРИЯ"; else print "  чисто"
                }
                print ""
                print "  << МЕМОРИЯ = в эти секунды шла работа со swap/диском, тик ждал память"
                print "  чисто = ни памяти, ни троттлинга: причина в коде на главном потоке"
            }' "$SERVER_DIR/lag-events.log" "$OUTCPU" | tee -a "$OUT"
    fi
    say ""
    say "готово. Пришли $OUT"
    ;;
procs)  # что вообще ест память и CPU на машине
    : > "$OUT"
    say "=== кто на машине $(date '+%Y-%m-%d %H:%M:%S') ==="
    say "ядер: $(nproc), quota: $(cpu_quota), load: $(cut -d' ' -f1-3 /proc/loadavg)"
    say ""
    say "--- память (МБ) ---"
    while IFS= read -r l; do say "  $l"; done <<EOF
$(free -m)
EOF
    say ""
    say "--- swap ---"
    while IFS= read -r l; do say "  $l"; done <<EOF
$(cat /proc/swaps 2>/dev/null || echo "нет swap")
EOF
    say ""
    say "--- топ процессов по памяти ---"
    while IFS= read -r l; do say "  $l"; done <<EOF
$(ps -eo pid,rss,etime,rss,args --sort=-rss 2>/dev/null | head -12 | cut -c1-150)
EOF
    say ""
    say "--- java-процессы ---"
    n=0
    for p in $(pgrep -x java 2>/dev/null); do
        n=$(( n + 1 ))
        say "  pid $p  rss=$(awk '/VmRSS/ { print int($2 / 1024) }' "/proc/$p/status" 2>/dev/null) МБ  живёт: $(ps -o etime= -p "$p" 2>/dev/null | tr -d ' ')  cmd: $(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null | cut -c1-110)"
    done
    [ "$n" = "0" ] && say "  java-процессов нет"
    say "  всего java: $n"
    if [ "$n" -gt 1 ]; then
        say ""
        say "  >>> ВНИМАНИЕ: java-процессов больше одного — второй держит память и swap"
        say "      и может драться за файлы мира. Лишний убивается: kill <pid>"
    fi
    say ""
    say "  потоков в системе: $(ps -eLf 2>/dev/null | tail -n +2 | wc -l)"
    say "  готово. Пришли $OUT"
    ;;
watch)  # ждём медленный тик по логу и сразу снимаем JFR
    if [ -z "$PID" ]; then echo "процесс сервера не найден" >&2; exit 1; fi
    JCMD=$(tool jcmd) || { echo "не найден jcmd" >&2; exit 1; }
    THRESHOLD=${4:-150}
    LOGF=${5:-logs/latest.log}
    [ -f "$LOGF" ] || { echo "нет $LOGF" >&2; exit 1; }
    echo "жду в $LOGF строки 'lasted N ms' с N >= $THRESHOLD; снимок -> $SERVER_DIR/lag-*.jfr"
    echo "остановить: Ctrl+C"
    tail -n0 -F "$LOGF" 2>/dev/null | while IFS= read -r line; do
        case "$line" in
            *lasted*ms*) ;;
            *) continue ;;
        esac
        ms=$(printf '%s' "$line" | sed -n 's/.*lasted \([0-9][0-9]*\).*/\1/p')
        [ -z "$ms" ] && continue
        [ "$ms" -lt "$THRESHOLD" ] && continue
        ts=$(date +%Y%m%d-%H%M%S)
        echo ">>> $ms ms: снимаю JFR в lag-$ts.jfr"
        printf '%s\n' "[$(date '+%H:%M:%S')] $line" >> "$SERVER_DIR/lag-events.log"
        "$JCMD" "$PID" JFR.dump name="$NAME" filename="$SERVER_DIR/lag-$ts.jfr" >/dev/null 2>&1 \
            && echo "    готово: lag-$ts.jfr" || echo "    не удалось снять (запись JFR запущена?)"
    done
    ;;
deep)  # полные стеки: кто читает файлы, кто аллоцирует, кто паркуется
    JFR=$(tool jfr) || { echo "не найден jfr (JDK 21+)" >&2; exit 1; }
    [ -f "$JFR_FILE" ] || { echo "нет файла $JFR_FILE" >&2; exit 1; }
    : > "$OUT"
    say "=== JFR deep $(date '+%Y-%m-%d %H:%M:%S') ==="
    say "файл: $JFR_FILE"

    say ""
    say "--- какие файлы читаются (jdk.FileRead) ---"
    "$JFR" print --events jdk.FileRead "$JFR_FILE" 2>/dev/null | awk '
        function tobytes(v, u) { if (u == "kB") return v * 1000; if (u == "MB") return v * 1000000; if (u == "GB") return v * 1000000000; return v }
        /^jdk\.FileRead \{/ { inp = 1; pth = ""; b = 0; d = 0; n = 0; th = ""; inf = 0; fr[1] = ""; fr[2] = ""; fr[3] = ""; fr[4] = ""; next }
        inp && /^  path = "/ { split($0, a, "\""); pth = a[2] }
        inp && /^  bytesRead = / { b = tobytes($3, $4) }
        inp && /^  duration = / { d = $3 }
        inp && /^  eventThread = "/ { split($0, a, "\""); th = a[2] }
        inp && /stackTrace = \[/ { ins = 1; next }
        ins && /^  \]/ { ins = 0; next }
        ins && n < 4 { n++; fr[n] = $0; sub(/^ +/, "", fr[n]); sub(/ line:.*/, "", fr[n]) }
        inp && /^\}$/ {
            inp = 0
            fcnt[pth]++; fbytes[pth] += b; fms[pth] += d; fth[pth] = th
            k = th "  " pth
            for (i = 1; i <= n; i++) k = k " <- " fr[i]
            scnt[k]++
            next
        }
        END {
            print "  по файлам: читалось раз / сколько / кто:"
            m = 0; for (k in fcnt) ks[++m] = k
            for (i = 2; i <= m; i++) { x = ks[i]; j = i - 1; while (j > 0 && fcnt[ks[j]] < fcnt[x]) { ks[j+1] = ks[j]; j-- } ks[j+1] = x }
            for (i = 1; i <= m && i <= 10; i++) printf "  %6d  %10.0f kB  %8.1f ms  [%s]  %s\n", fcnt[ks[i]], fbytes[ks[i]] / 1000, fms[ks[i]], fth[ks[i]], ks[i]
        }' | tee -a "$OUT"

    say ""
    say "--- кто аллоцирует (jdk.ObjectAllocationSample, топ по весу) ---"
    "$JFR" print --events jdk.ObjectAllocationSample --stack-depth 12 "$JFR_FILE" 2>/dev/null | awk '
        function tobytes(v, u) { if (u == "kB") return v * 1000; if (u == "MB") return v * 1000000; if (u == "GB") return v * 1000000000; return v }
        /^jdk\.ObjectAllocationSample \{/ { inp = 1; cls = ""; w = 0; n = 0; inf = 0; fr[1] = ""; fr[2] = ""; next }
        inp && /^  objectClass = / { c = $0; sub(/^ +objectClass = /, "", c); sub(/ \(classLoader.*/, "", c); cls = c }
        inp && /^  weight = / { w = tobytes($3, $4) }
        inp && /stackTrace = \[/ { ins = 1; next }
        ins && /^  \]/ { ins = 0; next }
        ins && n < 6 { n++; fr[n] = $0; sub(/^ +/, "", fr[n]); sub(/ line:.*/, "", fr[n]) }
        inp && /^\}$/ {
            inp = 0
            key = cls
            for (i = 1; i <= n; i++) key = key "  <- " fr[i]
            wsum[key] += w; nsum[key]++
            next
        }
        END {
            m = 0; for (k in wsum) ks[++m] = k
            for (i = 2; i <= m; i++) { x = ks[i]; j = i - 1; while (j > 0 && wsum[ks[j]] < wsum[x]) { ks[j+1] = ks[j]; j-- } ks[j+1] = x }
            for (i = 1; i <= m && i <= 8; i++) printf "  %12.0f kB  (сэмплов %d)\n   %s\n", wsum[ks[i]] / 1000, nsum[ks[i]], ks[i]
        }' | tee -a "$OUT"

    say ""
    say "--- кто паркуется (jdk.ThreadPark) ---"
    "$JFR" print --events jdk.ThreadPark "$JFR_FILE" 2>/dev/null | awk '
        function dms(v, u) { if (u == "s") return v * 1000; if (u == "us") return v / 1000; return v }
        /^jdk\.ThreadPark \{/ { inp = 1; n = 0; th = ""; d = 0; inf = 0; fr[1] = ""; fr[2] = ""; next }
        inp && /^  duration = / { d = dms($3, $4) }
        inp && /^  eventThread = "/ { split($0, a, "\""); th = a[2] }
        inp && /stackTrace = \[/ { ins = 1; next }
        ins && /^  \]/ { ins = 0; next }
        ins && n < 5 { n++; fr[n] = $0; sub(/^ +/, "", fr[n]); sub(/ line:.*/, "", fr[n]) }
        inp && /^\}$/ {
            inp = 0
            k = th
            for (i = 1; i <= n; i++) k = k " <- " fr[i]
            cnt[k]++; ms[k] += d
            next
        }
        END {
            m = 0; for (k in cnt) ks[++m] = k
            for (i = 2; i <= m; i++) { x = ks[i]; j = i - 1; while (j > 0 && cnt[ks[j]] < cnt[x]) { ks[j+1] = ks[j]; j-- } ks[j+1] = x }
            for (i = 1; i <= m && i <= 8; i++) printf "  %7d  %10.0f ms  %s\n", cnt[ks[i]], ms[ks[i]], ks[i]
        }' | tee -a "$OUT"

    say ""
    say "готово. Пришли $OUT"
    ;;
window)  # события в окне +-N секунд вокруг HH:MM:SS
    CENTER=${3:-}
    if [ -z "$CENTER" ]; then echo "использование: bash $0 <папка> window HH:MM:SS [секунд] [файл]" >&2; exit 1; fi
    SPAN=${4:-10}
    WFILE=${5:-$JFR_FILE}
    JFR=$(tool jfr) || { echo "не найден jfr (JDK 21+)" >&2; exit 1; }
    [ -f "$WFILE" ] || { echo "нет файла $WFILE" >&2; exit 1; }
    IFS=: read -r hh mm ss <<< "$CENTER"
    t=$(( 10#$hh * 3600 + 10#$mm * 60 + 10#$ss ))
    LO=$(( t - SPAN )); [ "$LO" -lt 0 ] && LO=0
    HI=$(( t + SPAN ))
    : > "$OUT"
    say "=== JFR window $CENTER +-${SPAN} с : $(basename "$WFILE") ==="
    analyze_window "$WFILE" "$LO" "$HI"
    say ""
    say "готово. Пришли $OUT"
    ;;
windows)  # разобрать все lag-*.jfr, время берётся из имени файла
    SPAN=${3:-10}
    JFR=$(tool jfr) || { echo "не найден jfr (JDK 21+)" >&2; exit 1; }
    : > "$OUT"
    n=0
    for f in "$SERVER_DIR"/lag-*.jfr; do
        [ -f "$f" ] || continue
        b=$(basename "$f")
        c=$(printf '%s' "$b" | sed -n 's/^lag-[0-9]\{8\}-\([0-9]\{2\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)\.jfr$/\1:\2:\3/p')
        [ -z "$c" ] && continue
        IFS=: read -r hh mm ss <<< "$c"
        t=$(( 10#$hh * 3600 + 10#$mm * 60 + 10#$ss ))
        LO=$(( t - SPAN )); [ "$LO" -lt 0 ] && LO=0
        HI=$(( t + SPAN ))
        say "=== $b  (окно $c +-${SPAN} с) ==="
        analyze_window "$f" "$LO" "$HI"
        say ""
        n=$(( n + 1 ))
    done
    if [ "$n" = "0" ]; then
        say "файлов lag-*.jfr нет — watch ничего не снял"
    else
        say "разобрано файлов: $n. Пришли $OUT"
    fi
    ;;
start)
    : > "$OUT"
    if [ -z "$PID" ]; then echo "процесс сервера не найден" >&2; exit 1; fi
    JCMD=$(tool jcmd) || { echo "не найден jcmd — нужен полный JDK, не JRE" >&2; exit 1; }
    SETTINGS=profile
    EXTRA=""
    if [ "${HI:-0}" = "1" ]; then
        HIFILE=$(make_hi_jfc) && { SETTINGS=$HIFILE; EXTRA=" (сэмплы 2 мс)"; say "частая выборка: $HIFILE"; }
    fi
    say "=== JFR start $(date '+%Y-%m-%d %H:%M:%S') ==="
    say "pid: $PID, файл: $JFR_FILE, длительность: ${DURATION}s$EXTRA"
    chk=$("$JCMD" "$PID" JFR.check name="$NAME" 2>&1)
    case "$chk" in
        *"Could not find"*) : ;;
        *) say "останавливаю предыдущую запись '$NAME'"
           "$JCMD" "$PID" JFR.stop name="$NAME" >/dev/null 2>&1 || true ;;
    esac

    out=$("$JCMD" "$PID" JFR.start name="$NAME" settings="$SETTINGS" duration="${DURATION}s" filename="$JFR_FILE" 2>&1)
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
    say "--- ZGC allocation stall (поток ждал, пока GC освободит память) ---"
    "$JFR" print --events jdk.ZAllocationStall "$JFR_FILE" 2>/dev/null | awk '
        /^jdk\.ZAllocationStall \{/ { inp = 1; d = 0; t = ""; n = 0; next }
        inp && /^  startTime = / { t = $3 }
        inp && /^  duration = / { d = $3 + 0 }
        inp && /^\}$/ {
            inp = 0; cnt++; tot += d
            if (d > 15) { k++; dv[k] = d; tv[k] = t }
            next
        }
        END {
            if (cnt == 0) { print "  нет ни одного allocation stall"; exit }
            printf "  %d stall, суммарно %.0f ms\n", cnt, tot
            for (r = 0; r < 8; r++) {
                bi = 0
                for (i = 1; i <= k; i++) if (!used[i] && (bi == 0 || dv[bi] < dv[i])) bi = i
                if (!bi) break
                used[bi] = 1
                printf "    %s  %7.1f ms\n", tv[bi], dv[bi]
            }
        }' | tee -a "$OUT"

    say ""
    say "--- троттлинг CPU контейнера (если ВМ на квоте) ---"
    "$JFR" view --width 100 container-cpu-throttling "$JFR_FILE" 2>/dev/null | head -10 | tee -a "$OUT"

    say ""
    say "--- паузы GC ---"
    "$JFR" view --width 110 gc-pauses "$JFR_FILE" 2>/dev/null | head -22 | tee -a "$OUT"

    say ""
    say "--- горячие методы (сэмплы выполнения) ---"
    "$JFR" view --width 130 hot-methods "$JFR_FILE" 2>/dev/null | head -22 | tee -a "$OUT"

    say ""
    say "--- где время в native (сэмплы native-методов) ---"
    "$JFR" view --width 120 native-methods "$JFR_FILE" 2>/dev/null | head -16 | tee -a "$OUT"

    say ""
    say "--- кто аллоцирует (по стеку) ---"
    "$JFR" view --width 130 allocation-by-site "$JFR_FILE" 2>/dev/null | head -18 | tee -a "$OUT"

    say ""
    say "--- ожидание на блокировках ---"
    "$JFR" view --width 130 contention-by-site "$JFR_FILE" 2>/dev/null | head -14 | tee -a "$OUT"

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
