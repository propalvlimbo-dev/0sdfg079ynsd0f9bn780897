#!/usr/bin/env bash
# spark30.sh — сбор данных о лагах за окно наблюдения (обычно 30 минут).
#
#   bash spark30.sh /root/RW_GRIEF              — снимок "прямо сейчас" (10 секунд)
#   bash spark30.sh /root/RW_GRIEF report 30    — разбор logs/latest.log за 30 минут
#
# Зачем: spark за 30 минут покажет ОДИН общий профиль, где всплеск на 0.6 с
# утонет в 30 минутах нормальной работы. Поэтому в окне включаем два дешёвых
# текстовых счётчика (tickmonitor + редкие сэмплы), а потом считаем корреляцию
# по логу: "минуты с переподключениями websocket" против "минуты без них".
# Это доказательство со стороны сервера, без ссылок на клиент.
#
# Снимок сам по себе уже отличает "шторм переподключений" от обычной нагрузки:
#   * voluntary_ctxt_switches в /proc/<pid>/status (переключений контекста в сек);
#   * TIME_WAIT сокеты — каждый разорванный websocket оставляет один;
#   * число потоков процесса — WebSocketConnectReadThread плодит их на попытку.
set -u
export LC_ALL=C

SERVER_DIR=${1:-}
MODE=${2:-snapshot}
MINUTES=${3:-30}

if [ -z "$SERVER_DIR" ]; then
    echo "использование: bash $0 <папка_сервера> [report] [минут]" >&2
    exit 1
fi
cd "$SERVER_DIR" || { echo "нет каталога $SERVER_DIR" >&2; exit 1; }

OUT=spark30.txt

say() { printf '%s\n' "$*" | tee -a "$OUT"; }

find_pid() {
    local p
    p=$(pgrep -f 'server\.jar|leaf-|paper-' 2>/dev/null | head -1)
    [ -z "$p" ] && p=$(pgrep -f 'java .*Xmx' 2>/dev/null | head -1)
    printf '%s' "$p"
}

# --- счётчики ядра ----------------------------------------------------------
ctxt() {  # суммарные переключения контекста процесса
    awk '/^voluntary_ctxt_switches/ {v=$2} /^nonvoluntary_ctxt_switches/ {n=$2} END {print v+n}' \
        "/proc/$1/status" 2>/dev/null
}
threads() { awk '/^Threads/ {print $2}' "/proc/$1/status" 2>/dev/null; }
timewait() {
    if command -v ss >/dev/null 2>&1; then
        ss -tan 2>/dev/null | awk '$1=="TIME-WAIT"' | wc -l
    else
        cat /proc/net/tcp /proc/net/tcp6 2>/dev/null | awk 'NR>1 && $4=="06"' | wc -l
    fi
}

# --- режим 1: снимок --------------------------------------------------------
snapshot() {
    : > "$OUT"
    say "=== spark30: снимок $(date '+%Y-%m-%d %H:%M:%S') ==="
    say "каталог: $(pwd)"

    local pid; pid=$(find_pid)
    if [ -z "$pid" ]; then
        say "процесс сервера не найден — снимок невозможен"
        return 1
    fi
    say "pid: $pid"
    say "java: $(tr '\0' ' ' < "/proc/$pid/cmdline" | grep -o '\-Dblib[^ ]*' || echo 'нет -Dblib')"

    local c1 c2 t1 t2 w1 w2
    c1=$(ctxt "$pid"); t1=$(threads "$pid"); w1=$(timewait)
    sleep 10
    c2=$(ctxt "$pid"); t2=$(threads "$pid"); w2=$(timewait)

    local dc=$(( c2 - c1 )) dw=$(( w2 - w1 ))
    say ""
    say "за 10 секунд:"
    say "  переключений контекста: $dc  ($(( dc / 10 ))/сек)"
    say "  потоков: было $t1, стало $t2"
    local sign="+"; [ "$dw" -lt 0 ] && sign=""
    say "  TIME_WAIT сокетов: было $w1, стало $w2  ($sign$dw)"
    say ""
    say "  норма: до ~5000 переключений/сек, TIME_WAIT не растёт, потоков стабильно"
    say "  шторм переподключений: >20000/сек, TIME_WAIT растёт десятками за 10 с"

    if [ "${dc:-0}" -gt 20000 ] || [ "${dw:-0}" -gt 30 ]; then
        say ""
        say ">>> ВЕРДИКТ: похоже на шторм переподключений websocket."
        say "    Дальше: какой плагин — покажет report и поиск из lagdoctor.sh (п.1b)."
    fi

    local ws
    ws=$(grep -c '\[websocket\]' logs/latest.log 2>/dev/null || true)
    [ -n "$ws" ] && say "" && say "строк [websocket] в текущем latest.log: $ws"
    return 0
}

# --- режим 2: разбор лога ---------------------------------------------------
report() {
    : > "$OUT"
    say "=== spark30: разбор лога за последние ${MINUTES} мин ($(date '+%Y-%m-%d %H:%M:%S')) ==="

    local logf=logs/latest.log
    if [ ! -f "$logf" ]; then
        say "нет $logf"
        return 1
    fi

    local cut now pid
    cut=$(date -d "-${MINUTES} minutes" +%H:%M:%S)
    now=$(date +%H:%M:%S)
    pid=$(find_pid)

    say "окно: с $cut по $now, файл: $logf ($(wc -l < "$logf") строк)"
    [ -n "$pid" ] && say "java: $(tr '\0' ' ' < "/proc/$pid/cmdline" | grep -o '\-Dblib[^ ]*' || echo 'нет -Dblib')"
    say ""

    awk -v cut="$cut" -v now="$now" -v limit="$MINUTES" '
    function secs(t,  a) { split(t, a, ":"); return a[1]*3600 + a[2]*60 + a[3] }
    BEGIN { c = secs(cut); n0 = secs(now); wrap = (c > n0) }
    {
        t = substr($0, 2, 8)
        if (t !~ /^[0-9][0-9]:[0-9][0-9]:[0-9][0-9]$/) next
        s = secs(t)
        if (wrap) { keep = (s >= c || s <= n0) } else { keep = (s >= c) }
        if (!keep) next
        m = substr(t, 1, 5)
        if (index($0, "[websocket]") || index($0, "[OlI]")) { ws[m]++; totalWs++ }
        if (index($0, "included GC lasting")) { gc[m]++; totalGc++ }
        if (index($0, "Can not keep up") || index($0, "Can'\''t keep up")) ck++
        if (match($0, /lasted [0-9]+[.,]?[0-9]* ms/)) {
            v = substr($0, RSTART + 7, RLENGTH - 10); gsub(/,/, ".", v); v += 0
            slow[m]++; totalSlow++
            if (v > 100) slow100++
            k = ++n
            tms[k] = v; ttl[k] = t
        }
    }
    END {
        for (k in ws) mins[k] = 1
        for (k in slow) mins[k] = 1
        for (k in gc) mins[k] = 1

        # сортировка ключей минут по возрастанию
        cnt = 0
        for (k in mins) keys[++cnt] = k
        for (i = 2; i <= cnt; i++) {
            x = keys[i]; j = i - 1
            while (j > 0 && keys[j] > x) { keys[j+1] = keys[j]; j-- }
            keys[j+1] = x
        }

        print "  минута   ws=<переподключения>  slow=<тики >100 ms>  gc=<паузы GC>"
        for (i = 1; i <= cnt; i++) {
            k = keys[i]
            printf "  %s   ws=%-4d slow=%-3d gc=%d\n", k, ws[k], slow[k], gc[k]
            if (ws[k] > 0) { stormN++; stormSlow += slow[k]; stormGc += gc[k] }
            else { quietN++; quietSlow += slow[k]; quietGc += gc[k] }
        }

        print ""
        printf "  всего: websocket %d, медленных тиков %d (из них >100 ms: %d), GC-событий %d, \"Can not keep up\" %d\n", totalWs, totalSlow, slow100, totalGc, ck

        if (stormN > 0 && quietN > 0) {
            a = stormSlow / stormN
            b = (quietN > 0 ? quietSlow / quietN : 0)
            printf "\n  минуты С переподключениями: %d, в среднем %.1f медл.тика и %.1f GC на минуту\n", stormN, a, stormGc / stormN
            printf "  минуты БЕЗ них:            %d, в среднем %.1f медл.тика и %.1f GC на минуту\n", quietN, b, (quietN > 0 ? quietGc / quietN : 0)
            if (b > 0) printf "  отношение: %.1fx\n", a / b
            print ""
            if (b > 0 && a / b >= 2.0)
                print "  >>> ВЕРДИКТ: медленные тики сконцентрированы в минутах с переподключениями."
            else if (b > 0 && a / b < 1.5)
                print "  >>> ВЕРДИКТ: связи нет — переподключения не объясняют всплески, ищем дальше."
            else
                print "  >>> ВЕРДИКТ: связь слабая/неполная, нужно больше данных."
        } else if (stormN > 0) {
            print "\n  переподключения были, а нормальных минут в окне нет — окно слишком короткое"
        } else {
            print "\n  строк [websocket] в окне нет: либо плагин уже выключен, либо пишет не в latest.log"
        }

        if (n > 0) {
            print ""
            print "  самые медленные тики:"
            for (r = 0; r < 8; r++) {
                bi = 0
                for (i = 1; i <= n; i++) if (tms[i] > 0 && (bi == 0 || tms[i] > tms[bi])) bi = i
                if (!bi) break
                printf "    %s  %.1f ms\n", ttl[bi], tms[bi]
                tms[bi] = 0
            }
        }
    }' "$logf" | tee -a "$OUT"

    say ""
    say "готово. Пришли файл $OUT целиком (он короткий), либо строки выше."
}

case "$MODE" in
    report) report ;;
    *)      snapshot ;;
esac
