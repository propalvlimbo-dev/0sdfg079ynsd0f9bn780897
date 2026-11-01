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

find_pid() {  # среди java-процессов выбираем тот, что запущен из каталога сервера
    if [ -n "${JFR_PID:-}" ]; then printf '%s' "$JFR_PID"; return 0; fi
    local p rss best bestrss dir want match
    want=$(readlink -f "$SERVER_DIR" 2>/dev/null)
    best=""; bestrss=0; match=""
    for p in $(pgrep -x java 2>/dev/null); do
        [ "$(cat "/proc/$p/comm" 2>/dev/null)" = "java" ] || continue
        rss=$(awk '/^VmRSS:/ { print $2 + 0 }' "/proc/$p/status" 2>/dev/null)
        [ -z "$rss" ] && rss=0
        dir=$(readlink -f "/proc/$p/cwd" 2>/dev/null)
        [ -n "$want" ] && [ "$dir" = "$want" ] && match="$p"
        if [ "$rss" -gt "$bestrss" ]; then bestrss=$rss; best=$p; fi
    done
    [ -n "$match" ] && { printf '%s' "$match"; return 0; }
    printf '%s' "$best"
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
host_cpu() {  # $1=total $2=steal $3=iowait (тики)
    awk '/^cpu / { t = 0; for (i = 2; i <= NF; i++) t += $i; printf "%d %d %d\n", t, $9 + 0, $6 + 0; exit }' /proc/stat
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

analyze_blame() {  # $1 файл, $2 секунды от начала суток, $3 полуокно
    local HF=$1 SECS=$2 SP=${3:-6} JF
    LO=$(( SECS - SP )); [ "$LO" -lt 0 ] && LO=0
    HI=$(( SECS + SP ))
    JF=$(tool jfr) || { echo "не найден jfr (JDK 21+)"; return 1; }
    "$JF" print --events jdk.ExecutionSample,jdk.NativeMethodSample --stack-depth 16 "$HF" 2>/dev/null | awk -v lo="$LO" -v hi="$HI" '
        /^jdk\.[A-Za-z0-9_.]+ \{/ { ev = $1; inp = 1; th = ""; n = 0; inf = 0; split("", fr); next }
        inp && /^  startTime = / { st = $3; split(st, a, ":"); sec = a[1] * 3600 + a[2] * 60 + a[3] }
        inp && /^  sampledThread = "/ { split($0, a, "\""); th = a[2] }
        inp && /^  eventThread = "/ { if (th == "") { split($0, a, "\""); th = a[2] } }
        inp && /stackTrace = \[/ { inf = 1; next }
        inf && /^  \]/ { inf = 0; next }
        inf { n++; fr[n] = $0; sub(/^ +/, "", fr[n]); sub(/ line:.*/, "", fr[n]) }
        inp && /^\}$/ {
            inp = 0
            if (sec < lo || sec > hi) next
            total++
            if (index(th, "Server thread") != 1) next
            mine++
            k = ""
            for (i = 1; i <= n && i <= 4; i++) k = k (i > 1 ? " <- " : "") fr[i]
            cnt[k]++
            plug = ""
            for (i = 1; i <= n; i++) {
                f = fr[i]
                if (f ~ /^(net\.minecraft|java\.|javax\.|jdk\.|sun\.|io\.netty|it\.unimi|com\.mojang|ca\.spottedleaf|org\.bukkit|io\.papermc|com\.destroystokyo|gg\.pufferfish|org\.dreeam|org\.spigotmc|com\.google)/) continue
                plug = f; break
            }
            if (plug != "") { pcount[plug]++; if (!(plug in pfirst)) pfirst[plug] = k }
            next
        }
        END {
            printf "  сэмплов в окне: %d, из них Server thread: %d\n", total, mine
            if (mine == 0) { print "  по серверному потоку сэмплов нет"; exit }
            m = 0; for (k in cnt) ks[++m] = k
            for (i = 2; i <= m; i++) { x = ks[i]; j = i - 1
                while (j > 0 && cnt[ks[j]] < cnt[x]) { ks[j+1] = ks[j]; j-- }
                ks[j+1] = x }
            print ""
            print "  топ стеков Server thread:"
            for (i = 1; i <= m && i <= 12; i++) printf "  %4d  %5.1f%%  %s\n", cnt[ks[i]], cnt[ks[i]] * 100 / mine, ks[i]
            print ""
            mm = 0; for (q in pcount) pk[++mm] = q
            if (mm == 0) {
                print "  кадров из плагинов/библиотек нет: работал только серверный код"
            } else {
                for (i = 2; i <= mm; i++) { x = pk[i]; j = i - 1
                    while (j > 0 && pcount[pk[j]] < pcount[x]) { pk[j+1] = pk[j]; j-- }
                    pk[j+1] = x }
                print "  кадры из плагинов/библиотек (вне ванильного кода):"
                for (i = 1; i <= mm && i <= 10; i++) {
                    printf "  %4d  %s\n", pcount[pk[i]], pk[i]
                    printf "        стек: %s\n", pfirst[pk[i]]
                }
            }
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
        echo "# steal=процент ядер, отобранных гипервизором iow=ожидание диска в % ядер"
    } > "$OUTCPU"
    echo "пишу $OUTCPU каждую секунду, ${SECS} с. Проверить: tail -3 $OUTCPU   Остановить: Ctrl+C"
    t_end=$(( $(date +%s) + SECS ))
    prev_t=""; prev_u=""; prev_j=""; prev_i=""; prev_o=""; prev_f=""; prev_h=""; prev_s=0; prev_w=0
    while [ "$(date +%s)" -lt "$t_end" ]; do
        read -r th th_ms u <<< "$(cpu_stat)"
        j=$(jvm_ticks "$PID"); f=$(jvm_majflt "$PID")
        read -r h_total h_steal h_iowait <<< "$(host_cpu)"
        stl=0; iow=0
        if [ -n "$prev_h" ] && [ "$h_total" -gt "$prev_h" ]; then
            dt=$(( h_total - prev_h ))
            stl=$(( (h_steal - prev_s) * 100 / dt ))
            iow=$(( (h_iowait - prev_w) * 100 / dt ))
            [ "$stl" -lt 0 ] && stl=0
            [ "$iow" -lt 0 ] && iow=0
        fi
        prev_h=$h_total; prev_s=$h_steal; prev_w=$h_iowait
        i=$(vmstat_get pswpin); o=$(vmstat_get pswpout)
        if [ -z "$prev_t" ]; then
            line="$(date '+%H:%M:%S') thr=$th thr_ms=$th_ms cpu_ms=0 jvm=0 avail=$(mem_avail_mb) swap=$(swap_used_mb) swpin=0 swpout=0 majflt=0 psi_mem=$(psi_get memory)"
        else
            dj=$(( j - prev_j )); du=$(( u - prev_u ))
            di=$(( i - prev_i )); do_=$(( o - prev_o )); df=$(( f - prev_f ))
            [ "$du" -lt 0 ] && du=0
            line="$(date '+%H:%M:%S') thr=$th thr_ms=$th_ms cpu_ms=$du jvm=$(( dj * 100 / CLK )) avail=$(mem_avail_mb) swap=$(swap_used_mb) swpin=$di swpout=$do_ majflt=$df psi_mem=$(psi_get memory) steal=$stl iow=$iow"
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
    awk -v ncpu="$(nproc)" '
        /^#/ { next }
        {
            n++
            for (i = 2; i <= NF; i++) {
                split($i, kv, "="); k = kv[1]; v = kv[2] + 0
                if (k == "thr") th = v
                if (k == "thr_ms") thm = v
                if (k == "jvm") { jv = v; jvv[n] = v; if (v > maxjv) maxjv = v }
                if (k == "avail") { av = v; if (minav == "" || v < minav) { minav = v; minav_t = $1 } }
                if (k == "swap") { sw = v; if (v > maxsw) maxsw = v }
                if (k == "swpin") spi = v
                if (k == "swpout") spo = v
                if (k == "majflt") mf = v
                if (k == "psi_mem") { pm = v; if (v > maxpm) maxpm = v }
                if (k == "steal") { st = v; if (v > maxst) maxst = v }
                if (k == "iow") { iw = v; if (v > maxiw) maxiw = v }
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
            per_s = (n > 0 ? tot_spi / n : 0)
            if (per_s > 5 || tot_mf > n * 50) {
                print "  >>> память: swap реально читался обратно / много крупных page fault - тик ждал диск"
            } else if (maxsw > 0) {
                printf "  >>> память: в swap лежит %d МБ, но обратно читалось %.1f страниц/с - на тик это не влияет\n", maxsw, per_s
            } else {
                print "  >>> память: swap не использовался"
            }
            if (thi[n] == 0) print "  >>> троттлинга CPU-квоты не было (квоты на этой ВМ нет вообще)"
            # гистограмма CPU процесса
            m = 0
            for (i = 1; i <= n; i++) if (jvv[i] != "") jarr[++m] = jvv[i]
            for (i = 2; i <= m; i++) { x = jarr[i]; j = i - 1; while (j > 0 && jarr[j] > x) { jarr[j+1] = jarr[j]; j-- } jarr[j+1] = x }
            if (m > 0) {
                printf "  CPU процесса: медиана %d%%, p90 %d%%, p99 %d%%, пик %d%% (ядер: %d)\n", \
                    jarr[int(m * 0.5) + 1], jarr[int(m * 0.9) + 1], jarr[int(m * 0.99) + 1], jarr[m], ncpu
                busy = 0
                for (i = 1; i <= m; i++) if (jarr[i] >= ncpu * 85) busy++
                printf "  секунд, когда JVM забирала >=85%% всех ядер: %d из %d (%.1f%%)\n", busy, m, (m ? busy * 100 / m : 0)
            }
            printf "  гипервизор забрал (steal): максимум %d%% всех ядер; ожидание диска (iowait): максимум %d%%\n", maxst, maxiw
            if (maxst >= 20) print "  >>> STEAL: хост-машина отбирала процессор - сервер стоял не по своей вине"
            printf "  >>> CPU: пик %d%% ядра при %d ядрах в системе\n", maxjv, ncpu
            if (maxjv >= ncpu * 85 && maxst < 20) print "  >>> CPU насыщен: JVM забирает почти все ядра, тику не хватает процессора"
            save_n = n
        }' "$OUTCPU" | tee -a "$OUT"

    if [ -f "$SERVER_DIR/lag-events.log" ]; then
        say ""
        say "--- что было в момент каждого лага ---"
        awk -v ncpu="$(nproc)" '
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
                    if (k == "steal") sl[m] = v
                    if (k == "thr") th[m] = v
                    if (k == "thr_ms") thm[m] = v
                }
            }
            END {
                if (nl == 0) { print "  lag-events.log пуст"; exit }
                for (k = 1; k <= nl; k++) {
                    sMF = 0; sSP = 0; minA = -1; maxJ = 0; cnt = 0; maxTH = 0; maxSL = 0
                    for (i = 1; i <= m; i++) {
                        if (mt[i] >= lag[k] - 2 && mt[i] <= lag[k] + 10) {
                            cnt++; sMF += mf[i]; sSP += spi[i]
                            if (minA < 0 || av[i] < minA) minA = av[i]
                            if (jv[i] > maxJ) maxJ = jv[i]
                            if (i > 1 && th[i] > th[i-1]) maxTH = thm[i] - thm[i-1]
                            if (sl[i] > maxSL) maxSL = sl[i]
                        }
                    }
                    if (cnt == 0) { printf "  %s  нет данных (запись не шла)\n", lagtxt[k]; continue }
                    printf "  %s  faults %4d  swap-чт. %3d  свободно %4d МБ  CPU %3d%%  steal %2d%%", lagtxt[k], sMF, sSP, minA, maxJ, maxSL
                    if (maxSL >= 20) print "  << STEAL (процессор забрал гипервизор)"
                    else if (sMF > 500 || sSP > 10) print "  << МЕМОРИЯ"
                    else if (maxJ >= ncpu * 85) print "  << CPU (JVM заняла почти все ядра)"
                    else if (maxTH > 0) print "  << ТРОТТЛ"
                    else print "  ни память, ни CPU - причина в коде"
                }
                print ""
                print "  МЕМОРИЯ = в эти секунды шла работа со swap/диском, тик ждал диск"
                print "  CPU      = JVM занимала все ядра, тику не хватило процессора"
                print "  ТРОТТЛ   = срабатывала квота CPU контейнера"
                print "  STEAL    = процессор у сервера отбирала хост-машина"
                print "  ни память, ни CPU = причина в коде на главном потоке"
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
        say "  pid $p  rss=$(awk '/VmRSS/ { print int($2 / 1024) }' "/proc/$p/status" 2>/dev/null) МБ  живёт: $(ps -o etime= -p "$p" 2>/dev/null | tr -d ' ')"
        say "       каталог: $(readlink -f "/proc/$p/cwd" 2>/dev/null)"
        say "       cmd: $(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null | cut -c1-150)"
    done
    [ "$n" = "0" ] && say "  java-процессов нет"
    say "  всего java: $n"
    if [ "$n" -gt 1 ]; then
        say ""
        say "  >>> ВНИМАНИЕ: java-процессов больше одного — второй держит память и swap"
        say "      и может драться за файлы мира. Лишний убивается: kill <pid>"
    fi
    say ""
    say "--- кто слушает порты (java) ---"
    if command -v ss >/dev/null 2>&1; then
        while IFS= read -r l; do say "  $l"; done <<EOF
$(ss -tlnp 2>/dev/null | grep -E 'java|LISTEN' | head -20 | cut -c1-160)
EOF
    else
        say "  ss не установлен (apt install iproute2)"
    fi
    say ""
    say "  потоков в системе: $(ps -eLf 2>/dev/null | tail -n +2 | wc -l)"
    say "  готово. Пришли $OUT"
    ;;
blame)  # что делал Server thread в конкретном интервале: полные стеки
    HFILE=${3:-}
    CENTER=${4:-}
    SPAN=${5:-5}
    if [ -z "$HFILE" ] || [ ! -f "$HFILE" ]; then
        echo "использование: bash $0 <папка> blame <файл.jfr> HH:MM:SS [секунд]" >&2; exit 1
    fi
    [ -n "$CENTER" ] || { echo "нужно время: HH:MM:SS" >&2; exit 1; }
    JFR=$(tool jfr) || { echo "не найден jfr (JDK 21+)" >&2; exit 1; }
    IFS=: read -r hh mm ss <<< "$CENTER"
    t=$(( 10#$hh * 3600 + 10#$mm * 60 + 10#$ss ))
    : > "$OUT"
    say "=== blame: $(basename "$HFILE")  окно $CENTER +-${SPAN} с ==="
    analyze_blame "$HFILE" "$t" "$SPAN" | tee -a "$OUT"
    say ""
    say "готово. Пришли $OUT"
    ;;
session)  # один запуск: чистка, запись 90 мин, перехват и заметки
    MINUTES=${3:-90}
    echo "=== сессия записи на $MINUTES минут ==="
    echo "1/4 чищу старые процессы и дампы"
    pkill -f "jfr30[.]sh.*watch" 2>/dev/null && echo "   остановлены старые watch"
    rm -f "$SERVER_DIR"/lag-*.jfr "$SERVER_DIR"/part.jfr 2>/dev/null
    echo "2/4 запускаю запись JFR (частая выборка 2 мс, хранить последние 3 минуты)"
    HI=1 MAXAGE=3m MAXSIZE=300m bash "$0" "$SERVER_DIR" start $(( MINUTES * 60 )) || exit 1
    echo ""
    echo "3/4 запускаю перехват медленных тиков"
    nohup bash "$0" "$SERVER_DIR" watch 150 > "$SERVER_DIR/watch.log" 2>&1 &
    echo "   перехват в фоне (лог: $SERVER_DIR/watch.log)"
    echo "4/4 запускаю замер CPU/памяти/steal"
    pkill -f "jfr30[.]sh.*cpu " 2>/dev/null
    nohup bash "$0" "$SERVER_DIR" cpu $(( MINUTES * 60 )) > /dev/null 2>&1 &
    echo "   замер в фоне (лог: $SERVER_DIR/cpu.log)"
    echo ""
    echo "ГОТОВО. Дальше играйте как обычно, ничего не трогайте."
    echo ""
    echo "Не забудьте один раз в консоли сервера:  /spark tickmonitor --threshold-tick 150"
    echo ""
    echo "Когда случится лаг — выполнить:"
    echo "  bash $0 $SERVER_DIR catch"
    echo ""
    echo "Через $MINUTES минут всё остановится само."
    ;;
catch)  # найти последний лаг и сразу разобрать его
    if [ ! -f "$SERVER_DIR/lag-events.log" ]; then
        echo "нет $SERVER_DIR/lag-events.log — включён ли /spark tickmonitor?" >&2; exit 1
    fi
    echo "=== последние перехваченные тики ==="
    tail -5 "$SERVER_DIR/lag-events.log" | sed 's/^/  /'
    echo ""
    LAST=$(ls -t "$SERVER_DIR"/lag-*.jfr 2>/dev/null | head -1)
    if [ -z "$LAST" ]; then
        echo "дампов нет: либо лагов не было, либо запись JFR не идёт."
        echo "проверить запись: bash $0 $SERVER_DIR status"
        exit 1
    fi
    B=$(basename "$LAST")
    TIME=$(printf '%s' "$B" | sed -n 's/^lag-[0-9]\{8\}-\([0-9]\{2\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)\.jfr$/\1:\2:\3/p')
    echo "разбираю $B (момент $TIME, $(du -h "$LAST" | cut -f1))"
    echo ""
    bash "$0" "$SERVER_DIR" blame "$LAST" "$TIME" 6
    ;;
status)  # что сейчас запущено и пишется
    echo "=== состояние ==="
    if [ -n "$PID" ]; then
        echo "сервер: pid $PID, каталог $(readlink -f "/proc/$PID/cwd" 2>/dev/null)"
    else
        echo "сервер: процесс не найден"
    fi
    JCMD=$(tool jcmd) 2>/dev/null
    if [ -n "$PID" ] && [ -n "$JCMD" ]; then
        "$JCMD" "$PID" JFR.check name="$NAME" 2>&1 | tail -3
    fi
    echo ""
    echo "перехват: $(pgrep -cf "jfr30[.]sh.*watch") процессов"
    echo "замер CPU: $(pgrep -cf "jfr30[.]sh.*cpu ") процессов"
    echo "дампов: $(ls "$SERVER_DIR"/lag-*.jfr 2>/dev/null | wc -l), занимают $(du -sh --exclude=flight.jfr "$SERVER_DIR"/lag-*.jfr 2>/dev/null | tail -1 | cut -f1)"
    echo "лаб-событий: $(grep -c '' "$SERVER_DIR/lag-events.log" 2>/dev/null || echo 0)"
    if [ -f "$SERVER_DIR/lag-events.log" ]; then
        CUT=$(date -d '-10 minutes' +%H:%M:%S 2>/dev/null)
        FRESH=$(awk -v cut="$CUT" '{ t = substr($0, 2, 8); if (t >= cut) c++ } END { print c + 0 }' "$SERVER_DIR/lag-events.log" 2>/dev/null)
        echo "за последние 10 минут новых: $FRESH"
        if [ "$FRESH" = "0" ]; then
            echo "  >>> похоже, /spark tickmonitor не включён — перехват нечего ловить."
            echo "      в консоли сервера: /spark tickmonitor --threshold-tick 150"
        fi
    fi
    echo "строк cpu.log: $(grep -c '' "$SERVER_DIR/cpu.log" 2>/dev/null || echo 0)"
    ;;
tasks)  # кто создаёт задачи в планировщике (виновник очереди CraftScheduler)
    HFILE=${3:-$SERVER_DIR/now.jfr}
    [ -f "$HFILE" ] || HFILE=$JFR_FILE
    [ -f "$HFILE" ] || { echo "нет файла. bash $0 $SERVER_DIR now 120 - сначала сними" >&2; exit 1; }
    JFR=$(tool jfr) || { echo "не найден jfr (JDK 21+)" >&2; exit 1; }
    : > "$OUT"
    say "=== tasks: кто планирует задачи ($(basename "$HFILE")) ==="
    say ""

    "$JFR" print --events jdk.ObjectAllocationSample --stack-depth 16 "$HFILE" 2>/dev/null | awk -v self="$0" '
        /^jdk\.ObjectAllocationSample \{/ { inp = 1; cls = ""; n = 0; inf = 0; b = 0; next }
        BEGIN { tmin = -1; tmax = -1 }
        inp && /^  objectClass = / { c = $0; sub(/^ +objectClass = /, "", c); sub(/ \(classLoader.*/, "", c); cls = c }
        inp && /^  weight = / {
            w = $3 + 0; u = $4
            if (u ~ /^k/) b = w * 1024
            else if (u ~ /^M/) b = w * 1048576
            else if (u ~ /^G/) b = w * 1073741824
            else b = w
            next
        }
        inp && /^  startTime = / {
            split($3, a, ":")
            v = a[1] * 3600 + a[2] * 60 + a[3]
            if (tmin < 0 || v < tmin) tmin = v
            if (v > tmax) tmax = v
            next
        }
        inp && /stackTrace = \[/ { inf = 1; next }
        inf && /^  \]/ { inf = 0; next }
        inf { n++; fr[n] = $0; sub(/^ +/, "", fr[n]); sub(/ line:.*/, "", fr[n]) }
        inp && /^\}$/ {
            inp = 0
            if (cls !~ /CraftTask|CraftScheduler|ServerSchedulerReportingWrapper|ScheduledTask|CraftAsyncTask|BukkitTask/) next
            # берём замыкание: первый кадр вне серверного/букит-кода — это и есть вызывающий плагин
            caller = ""
            for (i = 1; i <= n; i++) {
                f = fr[i]
                if (f ~ /^(org\.bukkit|io\.papermc|com\.destroystokyo|net\.minecraft|java\.|javax\.|jdk\.|sun\.|com\.google|it\.unimi|ca\.spottedleaf)/) continue
                caller = f; break
            }
            if (caller == "") caller = "(сервер/якорь без плагина) " fr[2]
            k = cls "  <- " caller
            cnt[k]++
            bytes[k] += b
            if (!(k in ex)) { ex[k] = ""; for (i = 1; i <= n && i <= 6; i++) ex[k] = ex[k] (i > 1 ? " <- " : "") fr[i] }
            next
        }
        END {
            if (length(cnt) == 0) { print "  задач в этом файле не создавалось (или выборка не поймала)"; exit }
            span = (tmax > tmin && tmin >= 0) ? tmax - tmin : 0
            m = 0; for (k in cnt) ks[++m] = k
            for (i = 2; i <= m; i++) { x = ks[i]; j = i - 1
                while (j > 0 && bytes[ks[j]] < bytes[x]) { ks[j+1] = ks[j]; j-- }
                ks[j+1] = x }
            total = 0
            for (k in bytes) total += bytes[k]
            printf "  окно наблюдения: %d с\n", span
            if (total > 0) printf "  всего аллокаций на объекты задач: %.1f MB\n", total / 1048576
            print ""
            print "  источник (по объёму аллокаций):"
            for (i = 1; i <= m && i <= 12; i++) {
                share = total > 0 ? bytes[ks[i]] * 100 / total : 0
                if (span > 0) printf "  %7.1f MB  %4.1f%%  %6.2f MB/мин  %s\n", bytes[ks[i]] / 1048576, share, bytes[ks[i]] / 1048576 * 60 / span, ks[i]
                else printf "  %7.1f MB  %4.1f%%  %s\n", bytes[ks[i]] / 1048576, share, ks[i]
                printf "           %s\n", ex[ks[i]]
            }
            print ""
            top = ks[1]; topshare = total > 0 ? bytes[top] * 100 / total : 0
            split(top, tp, "  <- ")
            if (topshare >= 50)
                printf "  >>> %.0f%% всего объёма даёт ОДИН источник: %s\n", topshare, tp[2]
            if (tp[2] ~ /com\.comphenix\.protocol/)
                print "      ProtocolLib планирует задачу на главный поток на КАЖДЫЙ пакет,\n      у которого есть синхронный слушатель, отправленный не из главного потока.\n      Кто слушает исходящие пакеты: bash " self " <папка> psend"
        }' | tee -a "$OUT"

    say ""
    say "готово. Пришли $OUT"
    ;;
psend)  # какие плагины слушают исходящие пакеты через ProtocolLib
    PD=$SERVER_DIR/plugins
    [ -d "$PD" ] || { echo "нет каталога $PD" >&2; exit 1; }
    : > "$OUT"
    say "=== psend: у кого есть слушатель ИСХОДЯЩИХ пакетов (onPacketSending) ==="
    say ""
    TMP=$(mktemp)
    for j in "$PD"/*.jar; do
        [ -f "$j" ] || continue
        c=$(timeout 30 unzip -p "$j" '*.class' 2>/dev/null | grep -ac 'onPacketSending')
        [ "${c:-0}" -gt 0 ] || continue
        a=$(timeout 30 unzip -p "$j" '*.class' 2>/dev/null | grep -ac 'com/comphenix/protocol/events/PacketAdapter')
        printf '%5d %5d %s\n' "$c" "$a" "$(basename "$j")" >> "$TMP"
    done
    if [ -s "$TMP" ]; then
        say "  класс-файлов с onPacketSending | ссылок на PacketAdapter | jar"
        sort -rn "$TMP" | while read -r c a j; do printf "  %5d  %5d  %s\n" "$c" "$a" "$j"; done | tee -a "$OUT"
        say ""
        say "  Плагин с onPacketSending и есть тот, из-за кого ProtocolLib гоняет каждый"
        say "  исходящий пакет в главный поток. Если он умеет ASYNC-слушатели —"
        say "  включи их; если это античит вроде Florium — выключи в нём хук ProtocolLib."
    else
        say "  onPacketSending не найден ни в одном jar (слушатели могут быть в libs/ или"
        say "  регистрироваться через прокси-методы) — пришли список: ls $PD"
    fi
    rm -f "$TMP"
    say ""
    say "готово. Пришли $OUT"
    ;;
waits)  # кто тормозил: файлы, сокеты, парковки, локи дольше порога
    TH=${3:-50}
    WFILE=${4:-$SERVER_DIR/now.jfr}
    [ -f "$WFILE" ] || WFILE=$JFR_FILE
    [ -f "$WFILE" ] || { echo "нет файла. bash $0 $SERVER_DIR now 120" >&2; exit 1; }
    JFR=$(tool jfr) || { echo "не найден jfr (JDK 21+)" >&2; exit 1; }
    : > "$OUT"
    say "=== waits: где поток ЖДАЛ дольше ${TH} мс ($(basename "$WFILE")) ==="
    say "    (выборка ловит только работающий поток; тик, который 2 с ждал диск/лок, виден тут)"
    say ""
    "$JFR" print --events jdk.FileWrite,jdk.FileRead,jdk.FileForce,jdk.SocketRead,jdk.SocketWrite,jdk.ThreadPark,jdk.JavaMonitorEnter,jdk.JavaMonitorWait --stack-depth 12 "$WFILE" 2>/dev/null | awk -v th="$TH" '
        /^jdk\.[A-Za-z0-9_.]+ \{/ { ev = $1; sub(/ \{/, "", ev); inp = 1; d = 0; thr = ""; n = 0; inf = 0; extra = ""; next }
        inp && /^  duration = / {
            v = $3 + 0; u = $4
            if (u ~ /^ns/) d = v / 1e6
            else if (u ~ /^us/ || u ~ /^µs/) d = v / 1e3
            else if (u ~ /^ms/) d = v
            else if (u ~ /^s/) d = v * 1000
            else d = v / 1e6
            next
        }
        inp && /^  eventThread = / { split($0, a, "\""); thr = a[2]; next }
        inp && /^  path = / { pp = $0; sub(/^ +path = /, "", pp); extra = extra " " pp; next }
        inp && /^  bytesWritten = / { extra = extra " записано=" $3; next }
        inp && /^  bytesRead = / { extra = extra " прочитано=" $3; next }
        inp && /^  timeout = / { extra = extra " timeout=" $3 "мс"; next }
        inp && /stackTrace = \[/ { inf = 1; next }
        inf && /^  \]/ { inf = 0; next }
        inf { n++; fr[n] = $0; sub(/^ +/, "", fr[n]); sub(/ line:.*/, "", fr[n]) }
        inp && /^\}$/ {
            inp = 0
            if (d < th) next
            m++; D[m] = d; E[m] = ev; T[m] = thr; X[m] = extra
            full = ""; for (i = 1; i <= n && i <= 12; i++) full = full (i > 1 ? " <- " : "") fr[i]
            F[m] = full
            next
        }
        END {
            if (m == 0) { printf "  событий дольше %d мс нет: поток не ждал, время ушло на CPU/GC\n", th; exit }
            for (i = 2; i <= m; i++) {
                xd = D[i]; xe = E[i]; xt = T[i]; xx = X[i]; xf = F[i]; j = i - 1
                while (j > 0 && D[j] < xd) { D[j+1] = D[j]; E[j+1] = E[j]; T[j+1] = T[j]; X[j+1] = X[j]; F[j+1] = F[j]; j-- }
                D[j+1] = xd; E[j+1] = xe; T[j+1] = xt; X[j+1] = xx; F[j+1] = xf
            }
            printf "  событий дольше %d мс: %d, самое долгое %.0f мс\n\n", th, m, D[1]
            for (i = 1; i <= m && i <= 15; i++) {
                printf "  %8.1f мс  %s  [%s]%s\n", D[i], E[i], T[i], X[i]
                printf "           %s\n", F[i]
            }
        }' | tee -a "$OUT"
    say ""
    say "готово. Пришли $OUT"
    ;;
spikes)  # где именно секундные всплески главного потока (для «фриз на 1 секунду»)
    N=${3:-10}
    SFILE=${4:-$SERVER_DIR/now.jfr}
    [ -f "$SFILE" ] || SFILE=$JFR_FILE
    [ -f "$SFILE" ] || { echo "нет файла. bash $0 $SERVER_DIR now 120" >&2; exit 1; }
    JFR=$(tool jfr) || { echo "не найден jfr (JDK 21+)" >&2; exit 1; }
    : > "$OUT"
    say "=== spikes: сэмплы Server thread по секундам ($(basename "$SFILE")) ==="
    say ""
    "$JFR" print --events jdk.ExecutionSample --stack-depth 4 "$SFILE" 2>/dev/null | awk '
        /^jdk\.ExecutionSample \{/ { inp = 1; th = ""; n = 0; inf = 0; next }
        inp && /^  startTime = / { split($3, a, ":"); t = a[1] * 3600 + a[2] * 60 + a[3]; next }
        inp && /^  sampledThread = "/ { split($0, a, "\""); th = a[2]; next }
        inp && /stackTrace = \[/ { inf = 1; next }
        inf && /^  \]/ { inf = 0; next }
        inf { n++; leaf[n] = $0; sub(/^ +/, "", leaf[n]); sub(/ line:.*/, "", leaf[n]) }
        inp && /^\}$/ {
            inp = 0
            if (th != "Server thread") next
            s = int(t)
            cnt[s]++
            total++
            if (n >= 1) l1[s, leaf[1]]++
            if (n >= 2) l2[s, leaf[2]]++
            if (s < lo || lo == 0) lo = s
            if (s > hi) hi = s
            next
        }
        END {
            if (total == 0) { print "  сэмплов Server thread нет"; exit }
            span = hi - lo + 1
            m = 0; for (s in cnt) { m++; ss[m] = s + 0; cs[m] = cnt[s] }
            for (i = 2; i <= m; i++) { x = cs[i]; j = i - 1
                while (j > 0 && cs[j] > x) { cs[j+1] = cs[j]; j-- }
                cs[j+1] = x }
            mid = (m % 2) ? cs[(m+1)/2] : (cs[m/2] + cs[m/2+1]) / 2
            if (mid < 1) mid = 1
            mx = 0; for (s in cnt) if (cnt[s] > mx) { mx = cnt[s]; mxs = s }
            printf "  секунд с сэмплами: %d, всего сэмплов: %d\n", m, total
            printf "  в среднем %.1f сэмпла/с, медиана %.0f, пик %d\n\n", total / span, mid, mx
            # сортировка секунд по числу сэмплов
            for (i = 2; i <= m; i++) { x = ss[i]; j = i - 1
                while (j > 0 && cnt[ss[j]] < cnt[x + 0]) { ss[j+1] = ss[j]; j-- }
                ss[j+1] = x }
            printf "  самые горячие секунды (порог всплеска: 3x медианы = %.0f):\n", mid * 3
            for (i = 1; i <= m && i <= 10; i++) {
                s = ss[i]
                hh = int(s / 3600); mm = int((s % 3600) / 60); ssc = s % 60
                mark = (cnt[s] >= mid * 3) ? "  <<< ВСПЛЕСК" : ""
                printf "  %02d:%02d:%02d  %4d сэмплов%s\n", hh, mm, ssc, cnt[s], mark
                # два самых частых листовых кадра этой секунды
                delete top; k = 0
                for (f in l1) { split(f, p, SUBSEP); if (p[1] != s) continue; k++; top[k] = f }
                for (x1 = 2; x1 <= k; x1++) { y = top[x1]; z = x1 - 1
                    while (z > 0 && l1[top[z]] < l1[y]) { top[z+1] = top[z]; z-- }
                    top[z+1] = y }
                for (x1 = 1; x1 <= k && x1 <= 3; x1++) {
                    split(top[x1], p, SUBSEP)
                    printf "        %4d  %s\n", l1[top[x1]], p[2]
                }
            }
            if (m < 3) print "  (секунд мало: окно короче 3 с, статистика грубая)"
        }' | tee -a "$OUT"
    say ""
    say "готово. Пришли $OUT"
    ;;
now)  # снять и разобрать ПРЯМО СЕЙЧАС, не дожидаясь строки в логе
    SPAN=${3:-120}
    if [ -z "$PID" ]; then echo "процесс сервера не найден" >&2; exit 1; fi
    JCMD=$(tool jcmd) || { echo "не найден jcmd (JDK 21+)" >&2; exit 1; }
    JFR=$(tool jfr) || { echo "не найден jfr (JDK 21+)" >&2; exit 1; }
    PART=$SERVER_DIR/now.jfr
    rm -f "$PART"
    echo "снимаю текущую запись (последние минуты) -> $PART"
    "$JCMD" "$PID" JFR.dump name="$NAME" filename="$PART" >/dev/null 2>&1 || true
    if [ ! -f "$PART" ]; then
        # запись живёт внутри JVM — после перезапуска сервера её нет
        echo "  записи нет (она не переживает рестарт сервера). Завожу новую."
        SETTINGS=profile
        EXTRA=""
        if [ "${HI:-0}" = "1" ]; then
            HIFILE=$(make_hi_jfc) && { SETTINGS=$HIFILE; EXTRA=" (сэмплы 2 мс)"; }
        fi
        EXTRA_ARGS=()
        [ -n "${MAXAGE:-}" ] && EXTRA_ARGS+=("maxage=$MAXAGE")
        [ -n "${MAXSIZE:-}" ] && EXTRA_ARGS+=("maxsize=$MAXSIZE")
        st=$("$JCMD" "$PID" JFR.start name="$NAME" settings="$SETTINGS" duration="$(( SPAN + 60 ))s" filename="$JFR_FILE" "${EXTRA_ARGS[@]}" 2>&1)
        case "$st" in
            *[Ss]tarted*) : ;;
            *) echo "не смог запустить запись: $st" >&2; exit 1 ;;
        esac
        echo "  запись идёт${EXTRA}, жду ${SPAN} с — это и есть время наблюдения..."
        W=0
        while [ "$W" -lt "$SPAN" ]; do
            sleep 5; W=$((W + 5)); [ "$W" -gt "$SPAN" ] && W=$SPAN
            printf '\r  собрано: %ss / %ss' "$W" "$SPAN"
        done
        printf '\r%s\r' "                                        "
        "$JCMD" "$PID" JFR.dump name="$NAME" filename="$PART" >/dev/null 2>&1 || true
    fi
    [ -f "$PART" ] || { echo "файл не создан — пришли вывод: bash $0 $SERVER_DIR status" >&2; exit 1; }
    echo "готово: $(du -h "$PART" | cut -f1)"
    echo ""

    LAST=$("$JFR" print --events jdk.ExecutionSample --stack-depth 2 "$PART" 2>/dev/null | awk '
        /^  startTime = / { split($3, a, ":"); v = a[1] * 3600 + a[2] * 60 + a[3]; if (v > mx) mx = v }
        END { printf "%d", mx }')
    [ -z "$LAST" ] && LAST=0
    printf -v HM '%02d:%02d:%02d' $(( LAST / 3600 )) $(( (LAST % 3600) / 60 )) $(( LAST % 60 ))
    : > "$OUT"
    say "=== now: разбор последних ${SPAN} с (до $HM) ==="
    echo ""
    analyze_blame "$PART" "$LAST" "$SPAN" | tee -a "$OUT"

    echo ""
    echo "--- GC, safepoint и ZGC-сталлы в этом же файле ---"
    "$JFR" print --events jdk.GCPhasePause,jdk.SafepointBegin,jdk.ZAllocationStall,jdk.GarbageCollection "$PART" 2>/dev/null |
    awk '
        /^jdk\.[A-Za-z0-9_.]+ \{/ { ev = $1; inp = 1; d = 0; next }
        inp && /^  duration = / { d = $3 + 0 }
        inp && /^\}/ { inp = 0; if (d >= 50) { m++; dv[m] = d; evn[m] = ev } next }
        END {
            if (m == 0) { print "  событий >= 50 мс нет"; exit }
            for (i = 2; i <= m; i++) { x = dv[i]; y = evn[i]; j = i - 1
                while (j > 0 && dv[j] < x) { dv[j+1] = dv[j]; evn[j+1] = evn[j]; j-- }
                dv[j+1] = x; evn[j+1] = y }
            for (i = 1; i <= m && i <= 10; i++) printf "  %8.1f ms  %s\n", dv[i], evn[i]
        }' | tee -a "$OUT"
    echo ""
    echo "готово. Пришли $OUT"
    ;;
top)  # самые тяжёлые лаги из lag-events.log -> разбор каждого
    N=${3:-3}
    SPAN=${4:-6}
    [ -f "$SERVER_DIR/lag-events.log" ] || { echo "нет lag-events.log — включён ли /spark tickmonitor?" >&2; exit 1; }
    : > "$OUT"
    say "=== top: самые тяжёлые лаги ==="

    # 1. разобрать лог: время + миллисекунды, отсортировать по длительности
    awk '
        {
            t = substr($0, 2, 8)
            if (t !~ /^[0-9][0-9]:[0-9][0-9]:[0-9][0-9]$/) next
            if (!match($0, /lasted [0-9]+/)) next
            v = substr($0, RSTART + 7, RLENGTH - 7) + 0
            key = t " " v
            if (key in seen) next
            seen[key] = 1
            split(t, a, ":"); sec = a[1] * 3600 + a[2] * 60 + a[3]
            n++; S[n] = sec; M[n] = v; T[n] = t
        }
        END {
            for (i = 2; i <= n; i++) { x = M[i]; y = S[i]; z = T[i]; j = i - 1
                while (j > 0 && M[j] < x) { M[j+1] = M[j]; S[j+1] = S[j]; T[j+1] = T[j]; j-- }
                M[j+1] = x; S[j+1] = y; T[j+1] = z }
            printf "%d\n", n
            for (i = 1; i <= n; i++) printf "%d %d %s\n", S[i], M[i], T[i]
        }' "$SERVER_DIR/lag-events.log" > "$SERVER_DIR/.lags.sorted"

    TOTAL=$(head -1 "$SERVER_DIR/.lags.sorted")
    say "  разных медленных тиков в логе: $TOTAL"
    say ""

    # 2. показать топ
    take=$N
    [ "$TOTAL" -lt "$take" ] && take=$TOTAL
    say "  топ-$take по длительности:"
    sed -n "2,$(( take + 1 ))p" "$SERVER_DIR/.lags.sorted" | awk '{ printf "    %s  %6d ms\n", $3, $2 }' | tee -a "$OUT"
    say ""

    # 3. разобрать каждый
    seq=0
    while read -r sec ms hm; do
        seq=$(( seq + 1 ))
        [ "$seq" -gt "$take" ] && break
        say "----- лог $hm, $ms ms -----"

        best=""; bestt=0
        for f in "$SERVER_DIR"/lag-*.jfr; do
            [ -f "$f" ] || continue
            b=$(basename "$f")
            ct=$(printf '%s' "$b" | sed -n 's/^lag-[0-9]\{8\}-\([0-9]\{2\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)\.jfr$/\1:\2:\3/p')
            [ -z "$ct" ] && continue
            IFS=: read -r ch cm cs <<< "$ct"
            csec=$(( 10#$ch * 3600 + 10#$cm * 60 + 10#$cs ))
            d=$(( csec - sec ))
            # снимок должен быть сделан после лага и не позже 3 минут (maxage)
            if [ "$d" -ge 0 ] && [ "$d" -le 180 ]; then
                if [ -z "$best" ] || [ "$d" -lt "$bestt" ]; then best=$f; bestt=$d; fi
            fi
        done

        if [ -z "$best" ]; then
            say "  снимка нет (перехват пропустил этот тик)"
            say ""
            continue
        fi
        say "  снимок: $(basename "$best") (+${bestt} с)"
        analyze_blame "$best" "$sec" "$SPAN"
        say ""
    done < <(sed -n "2,$(( take + 1 ))p" "$SERVER_DIR/.lags.sorted")

    rm -f "$SERVER_DIR/.lags.sorted"
    say "готово. Пришли $OUT"
    ;;
freeze)  # ищем провалы: когда ВСЯ JVM не выдавала ни одного сэмпла
    HFILE=${3:-$(ls -t "$SERVER_DIR"/lag-*.jfr "$SERVER_DIR"/flight.jfr 2>/dev/null | head -1)}
    MINMS=${4:-500}
    [ -f "$HFILE" ] || { echo "нет файла. bash $0 $SERVER_DIR freeze путь.jfr [мс]" >&2; exit 1; }
    JFR=$(tool jfr) || { echo "не найден jfr (JDK 21+)" >&2; exit 1; }
    : > "$OUT"
    say "=== freeze: $(basename "$HFILE") ($(du -h "$HFILE" | cut -f1)), провалы >= ${MINMS} мс ==="

    say ""
    say "--- провалы в сэмплах (в это время не работал ни один поток JVM) ---"
    "$JFR" print --events jdk.ExecutionSample,jdk.NativeMethodSample --stack-depth 4 "$HFILE" 2>/dev/null | awk -v minms="$MINMS" '
        function fmt(x,  h, m, sec) {
            h = int(x / 3600); x -= h * 3600; m = int(x / 60); sec = x - m * 60
            return sprintf("%02d:%02d:%02d.%03d", h, m, int(sec), int((sec - int(sec)) * 1000))
        }
        /^  startTime = / {
            t = $3; split(t, a, ":"); sec = a[1] * 3600 + a[2] * 60 + a[3]
            b = int(sec * 10)
            if (!(b in cnt)) { cnt[b] = 0; bth[b] = th; bfr[b] = fr[1]; bfr2[b] = fr[2] }
            cnt[b]++
            if (bmin == 0 || b < bmin) bmin = b
            if (b > bmax) bmax = b
            fr[1] = ""; fr[2] = ""
            next
        }
        /^  sampledThread = "/ { split($0, a, "\""); th = a[2]; next }
        /^  eventThread = "/ { if (th == "") { split($0, a, "\""); th = a[2] } next }
        /stackTrace = \[/ { inf = 1; n = 0; next }
        inf && /^  \]/ { inf = 0; next }
        inf && n < 2 { n++; fr[n] = $0; sub(/^ +/, "", fr[n]); sub(/ line:.*/, "", fr[n]) }
        END {
            want = int(minms / 100)
            gap = 0; gstart = 0; found = 0
            for (i = bmin; i <= bmax; i++) {
                if (!(i in cnt)) {
                    if (gap == 0) gstart = i
                    gap++
                } else {
                    if (gap >= want) {
                        found++
                        printf "  %s  провал %6.2f с\n", fmt(gstart / 10), gap / 10
                        if ((gstart - 1) in cnt)
                            printf "       до:    [%s] %s <- %s\n", bth[gstart-1], bfr[gstart-1], bfr2[gstart-1]
                        printf "       после: [%s] %s <- %s\n", bth[i], bfr[i], bfr2[i]
                    }
                    gap = 0
                }
            }
            print ""
            printf "  провалов всего: %d, окно записи: %s .. %s\n", found, fmt(bmin / 10), fmt(bmax / 10)
            if (found == 0) print "  >>> ни одной секунды простоя: JVM всё время что-то выполняла"
        }' | tee -a "$OUT"

    say ""
    say "--- паузы GC, safepoint и ZGC-сталлы >= 50 мс ---"
    "$JFR" print --events jdk.GCPhasePause,jdk.SafepointBegin,jdk.ZAllocationStall "$HFILE" 2>/dev/null | awk '
        function fmt(x,  h, m, sec) {
            h = int(x / 3600); x -= h * 3600; m = int(x / 60); sec = x - m * 60
            return sprintf("%02d:%02d:%02d.%03d", h, m, int(sec), int((sec - int(sec)) * 1000))
        }
        /^jdk\.[A-Za-z0-9_.]+ \{/ { ev = $1; inp = 1; d = 0; next }
        inp && /^  startTime = / { st = $3; split(st, a, ":"); sec = a[1] * 3600 + a[2] * 60 + a[3] }
        inp && /^  duration = / { d = $3 + 0 }
        inp && /^\}/ {
            inp = 0
            if (d >= 50 || ev ~ /ZAllocationStall/) { m++; dv[m] = d; tv[m] = sec; evn[m] = ev }
            next
        }
        END {
            if (m == 0) { print "  событий >= 50 мс нет"; exit }
            for (i = 2; i <= m; i++) { x = dv[i]; y = tv[i]; z = evn[i]; j = i - 1
                while (j > 0 && tv[j] > y) { dv[j+1] = dv[j]; tv[j+1] = tv[j]; evn[j+1] = evn[j]; j-- }
                dv[j+1] = x; tv[j+1] = y; evn[j+1] = z }
            for (i = 1; i <= m && i <= 25; i++) printf "  %s  %8.1f ms  %s\n", fmt(tv[i]), dv[i], evn[i]
        }' | tee -a "$OUT"

    say ""
    say "готово. Пришли $OUT"
    ;;
hunt)  # форензика по уже снятому дампу: что делал Server thread
    HFILE=${3:-$(ls -t "$SERVER_DIR"/lag-*.jfr "$SERVER_DIR"/flight.jfr 2>/dev/null | head -1)}
    TH=${4:-Server thread}
    [ -f "$HFILE" ] || { echo "нет файла. Укажи: bash $0 $SERVER_DIR hunt путь.jfr" >&2; exit 1; }
    JFR=$(tool jfr) || { echo "не найден jfr (JDK 21+)" >&2; exit 1; }
    : > "$OUT"
    say "=== hunt: $(basename "$HFILE") ($(du -h "$HFILE" | cut -f1)) ==="
    say "поток: $TH"
    say ""
    say "--- окно записи ---"
    "$JFR" summary "$HFILE" 2>/dev/null | sed -n '1,8p' | tee -a "$OUT"

    say ""
    say "--- топ методов [$TH]: сэмплы выполнения ---"
    "$JFR" print --events jdk.ExecutionSample,jdk.NativeMethodSample --stack-depth 12 "$HFILE" 2>/dev/null | awk -v want="$TH" '
        /^jdk\.[A-Za-z0-9_.]+ \{/ { ev = $1; inp = 1; th = ""; n = 0; inf = 0; fr[1] = ""; fr[2] = ""; fr[3] = ""; next }
        inp && /^  sampledThread = "/ { split($0, a, "\""); th = a[2] }
        inp && /^  eventThread = "/ { if (th == "") { split($0, a, "\""); th = a[2] } }
        inp && /stackTrace = \[/ { inf = 1; next }
        inf && /^  \]/ { inf = 0; next }
        inf && n < 3 { n++; fr[n] = $0; sub(/^ +/, "", fr[n]); sub(/ line:.*/, "", fr[n]) }
        inp && /^\}$/ {
            inp = 0; all++
            if (index(th, want) == 1) {
                mine++
                k = fr[1]
                if (fr[2] != "") k = k " <- " fr[2]
                if (fr[3] != "") k = k " <- " fr[3]
                cnt[k]++
                if (ev ~ /Native/) nat[k]++
            }
            next
        }
        END {
            printf "  сэмплов всего: %d, из них по потоку: %d\n", all, mine
            if (mine == 0) { print "  по этому потоку сэмплов нет - смотри native-методы и парки"; exit }
            m = 0; for (k in cnt) ks[++m] = k
            for (i = 2; i <= m; i++) { x = ks[i]; j = i - 1; while (j > 0 && cnt[ks[j]] < cnt[x]) { ks[j+1] = ks[j]; j-- } ks[j+1] = x }
            for (i = 1; i <= m && i <= 15; i++)
                printf "  %5d  %5.1f%%  %s%s\n", cnt[ks[i]], cnt[ks[i]] * 100 / mine, ks[i], (nat[ks[i]] ? "  [native]" : "")
        }' | tee -a "$OUT"

    say ""
    say "--- блокировки, ожидание GC и блокирующий ввод-вывод на [$TH] ---"
    "$JFR" print --events jdk.JavaMonitorEnter,jdk.SocketRead,jdk.FileRead,jdk.FileWrite,jdk.ZAllocationStall --stack-depth 8 "$HFILE" 2>/dev/null | awk -v want="$TH" '
        /^jdk\.[A-Za-z0-9_.]+ \{/ { ev = $1; inp = 1; th = ""; n = 0; inf = 0; dur = 0; fr[1] = ""; fr[2] = ""; fr[3] = ""; next }
        inp && /^  duration = / { dur = $3 + 0 }
        inp && /^  eventThread = "/ { split($0, a, "\""); th = a[2] }
        inp && /stackTrace = \[/ { inf = 1; next }
        inf && /^  \]/ { inf = 0; next }
        inf && n < 3 { n++; fr[n] = $0; sub(/^ +/, "", fr[n]); sub(/ line:.*/, "", fr[n]) }
        inp && /^\}$/ {
            inp = 0
            if (index(th, want) == 1) {
                k = ev "  " fr[1]
                if (fr[2] != "") k = k " <- " fr[2]
                cnt[k]++; ms[k] += dur
            }
            next
        }
        END {
            m = 0; for (k in cnt) ks[++m] = k
            if (m == 0) { print "  событий нет - поток не блокировался и не читал сокеты/файлы"; exit }
            for (i = 2; i <= m; i++) { x = ks[i]; j = i - 1; while (j > 0 && cnt[ks[j]] < cnt[x]) { ks[j+1] = ks[j]; j-- } ks[j+1] = x }
            for (i = 1; i <= m && i <= 12; i++) printf "  %6d  %10.0f ms  %s\n", cnt[ks[i]], ms[ks[i]], ks[i]
        }' | tee -a "$OUT"

    say ""
    say "--- GC и ZGC-сталлы в этом файле ---"
    "$JFR" print --events jdk.GarbageCollection,jdk.ZAllocationStall "$HFILE" 2>/dev/null | awk '
        /^jdk\.[A-Za-z0-9_.]+ \{/ { ev = $1; inp = 1; d = 0; t = ""; nm = ""; next }
        inp && /^  startTime = / { t = $3 }
        inp && /^  duration = / { d = $3 + 0 }
        inp && /^  name = "/ { split($0, a, "\""); nm = a[2] }
        inp && /^\}$/ {
            inp = 0
            if (ev !~ /GarbageCollection|ZAllocationStall/) next
            k = ev (nm != "" ? " (" nm ")" : "")
            cnt[k]++; tot[k] += d; m++
            dv[m] = d; tv[m] = t; evn[m] = k
            next
        }
        END {
            if (m == 0) { print "  ни сборок, ни ZGC-сталлов"; exit }
            for (k in cnt) printf "  %-45s %5d событий, %8.0f ms суммарно\n", k, cnt[k], tot[k]
            print ""
            print "  самые долгие:"
            for (r = 0; r < 10; r++) {
                bi = 0
                for (i = 1; i <= m; i++) if (!used[i] && (bi == 0 || dv[bi] < dv[i])) bi = i
                if (!bi) break
                used[bi] = 1
                printf "  %8.1f ms  %s  %s\n", dv[bi], tv[bi], evn[bi]
            }
        }' | tee -a "$OUT"

    say ""
    say "готово. Пришли $OUT"
    ;;
watch)  # ждём медленный тик по логу и сразу снимаем JFR
    if [ -z "$PID" ]; then echo "процесс сервера не найден" >&2; exit 1; fi
    JCMD=$(tool jcmd) || { echo "не найден jcmd" >&2; exit 1; }
    THRESHOLD=${3:-150}
    LOGF=${4:-logs/latest.log}
    COOLDOWN=${5:-30}
    last_dump=0
    [ -f "$LOGF" ] || { echo "нет $LOGF" >&2; exit 1; }
    echo "жду в $LOGF строки 'lasted N ms' с N >= $THRESHOLD; снимок -> $SERVER_DIR/lag-*.jfr"
    echo "между снимками не меньше $COOLDOWN с (иначе дамп сам создаёт лаги)"
    echo "остановить: Ctrl+C"
    tail -n0 -F "$LOGF" 2>/dev/null | while IFS= read -r line; do
        case "$line" in
            *lasted*ms*) ;;
            *) continue ;;
        esac
        ms=$(printf '%s' "$line" | sed -n 's/.*lasted \([0-9][0-9]*\).*/\1/p')
        [ -z "$ms" ] && continue
        [ "$ms" -lt "$THRESHOLD" ] && continue
        now=$(date +%s)
        if [ $(( now - last_dump )) -lt "$COOLDOWN" ]; then
            echo ">>> $ms ms: пропускаю, прошлый снимок $(( now - last_dump )) с назад"
            continue
        fi
        last_dump=$now
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
    say "pid: $PID, каталог процесса: $(readlink -f "/proc/$PID/cwd" 2>/dev/null), длительность: ${DURATION}s$EXTRA"
    say "java: $(tr '\0' ' ' < "/proc/$PID/cmdline" 2>/dev/null | cut -c1-140)"
    chk=$("$JCMD" "$PID" JFR.check name="$NAME" 2>&1)
    case "$chk" in
        *"Could not find"*) : ;;
        *) say "останавливаю предыдущую запись '$NAME'"
           "$JCMD" "$PID" JFR.stop name="$NAME" >/dev/null 2>&1 || true ;;
    esac

    EXTRA_ARGS=()
    [ -n "${MAXAGE:-}" ] && EXTRA_ARGS+=("maxage=$MAXAGE")
    [ -n "${MAXSIZE:-}" ] && EXTRA_ARGS+=("maxsize=$MAXSIZE")
    [ "${#EXTRA_ARGS[@]}" -gt 0 ] && say "хранить только последние: ${EXTRA_ARGS[*]}"
    out=$("$JCMD" "$PID" JFR.start name="$NAME" settings="$SETTINGS" duration="${DURATION}s" filename="$JFR_FILE" "${EXTRA_ARGS[@]}" 2>&1)
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
