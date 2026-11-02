#!/usr/bin/env bash
# conn.sh — почему сервер не пингуется и долго подключается.
# Проверяет всё, что может влиять, по порядку: порт -> очередь подключений ->
# локальный пинг -> внешний пинг -> DNS -> фаерволл -> ошибки в логе.
#
#   bash conn.sh /root/RW_GRIEF                 # полная проверка
#   bash conn.sh /root/RW_GRIEF play.example.ru # + проверка домена
#   bash conn.sh /root/RW_GRIEF --revert-mem    # снять лимиты нативной памяти
set -u
export LC_ALL=C

DIR=${1:-}
ARG=${2:-}
[ -n "$DIR" ] || { echo "использование: bash $0 <папка_сервера> [домен|--revert-mem]" >&2; exit 1; }
[ -d "$DIR" ] || { echo "нет каталога $DIR" >&2; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)
PORT=${PORT:-}
OUT=$DIR/conn-report.txt
say() { printf '%s\n' "$*" | tee -a "$OUT"; }

# --- откат лимитов нативной памяти -------------------------------------------
if [ "$ARG" = "--revert-mem" ]; then
    F=$DIR/start.sh
    [ -f "$F" ] || { echo "нет $F" >&2; exit 1; }
    [ -f "$F.bak" ] || cp "$F" "$F.now.bak"
    cp "$F" "$F.before-revert"
    awk '
        {
            line = $0
            # строка, состоящая только из нашего флага (возможно с \ в конце)
            if (line ~ /^[[:space:]]*-XX:(MaxDirectMemorySize|MaxMetaspaceSize)=[^[:space:]]*[[:space:]]*\\?[[:space:]]*$/) next
            # флаг внутри строки вместе с другими аргументами
            gsub(/[[:space:]]*-XX:(MaxDirectMemorySize|MaxMetaspaceSize)=[^[:space:]]*/, "")
            print
        }' "$F.before-revert" > "$F"
    if ! bash -n "$F"; then
        echo "после правки синтаксис сломан — возвращаю как было" >&2
        cp "$F.before-revert" "$F"; exit 1
    fi
    echo "убрал -XX:MaxDirectMemorySize и -XX:MaxMetaspaceSize из $F"
    grep -nE 'MaxDirectMemorySize|MaxMetaspaceSize' "$F" || echo "  (в файле их больше нет)"
    echo "дальше: обычный рестарт сервера"
    exit 0
fi

: > "$OUT"
say "=== conn: почему не пингуется ($(date '+%Y-%m-%d %H:%M:%S')) ==="
say ""

# --- 1. процесс и порт -------------------------------------------------------
PID=${JFR_PID:-}
if [ -z "$PID" ]; then
    want=$(readlink -f "$DIR")
    for p in $(pgrep -x java 2>/dev/null); do
        [ "$(readlink -f "/proc/$p/cwd" 2>/dev/null)" = "$want" ] && { PID=$p; break; }
    done
    [ -z "$PID" ] && PID=$(pgrep -x java 2>/dev/null | head -1)
fi
if [ -z "$PID" ]; then
    say "[1] ПРОЦЕСС: java не найден — сервер вообще запущен?"
else
    say "[1] ПРОЦЕСС: pid $PID, uptime $(ps -o etime= -p "$PID" 2>/dev/null | tr -d ' ')"
fi

if [ -z "$PORT" ]; then
    for f in "$DIR/server.properties"; do
        [ -f "$f" ] && PORT=$(awk -F= '/^server-port=/ { print $2; exit }' "$f")
    done
    [ -z "$PORT" ] && PORT=25565
fi
say "    порт сервера: $PORT"
say ""

# --- 2. слушает ли, и не забита ли очередь -----------------------------------
say "[2] ПОРТЫ И ОЧЕРЕДЬ ПОДКЛЮЧЕНИЙ"
if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | awk 'NR == 1 || /:25565|:25566|:25567|:20559|:8085/ { print "    " $0 }' | tee -a "$OUT"
    Q=$(ss -ltn 2>/dev/null | awk -v p=":$PORT" '$4 ~ p"$" { print $2 }' | head -1)
    SYN=$(ss -tan state syn-recv 2>/dev/null | tail -n +2 | wc -l)
    EST=$(ss -tan state established 2>/dev/null | awk -v p=":$PORT" '$4 ~ p"$"' | wc -l)
    say "    в очереди на accept (Recv-Q) для :$PORT = ${Q:-?}"
    say "    полуоткрытых (SYN-RECV) сейчас: $SYN"
    say "    установленных соединений на :$PORT: $EST"
    if [ "${Q:-0}" -gt 5 ] 2>/dev/null; then
        say "    >>> ОЧЕРЕДЬ ПОДКЛЮЧЕНИЙ ЗАБИТА. Это флуд/боты или сервер не успевает"
        say "        принимать. Пинг при этом висит, а вход идёт рывками."
    fi
else
    say "    нет ss, показываю netstat"
    netstat -ltn 2>/dev/null | awk 'NR <= 2 || /:25565|:25566|:25567/ { print "    " $0 }' | tee -a "$OUT"
fi
say ""

# --- 3. локальный пинг -------------------------------------------------------
say "[3] ЛОКАЛЬНЫЙ ПИНГ (127.0.0.1:$PORT)"
if command -v python3 >/dev/null 2>&1 && [ -f "$HERE/mpping.py" ]; then
    python3 "$HERE/mpping.py" 127.0.0.1 "$PORT" 3 2>&1 | tee -a "$OUT"
    LOCAL_OK=$?
else
    say "    нет python3 — пропускаю"
    LOCAL_OK=0
fi
say ""

# --- 4. внешний пинг по публичному IP ---------------------------------------
say "[4] ПИНГ ПО ВНЕШНЕМУ АДРЕСУ"
IP=$(curl -s --max-time 5 https://api.ipify.org 2>/dev/null || true)
[ -z "$IP" ] && IP=$(hostname -I 2>/dev/null | awk '{ print $1 }')
say "    внешний IP: ${IP:-не определился}"
if [ -n "$IP" ] && command -v python3 >/dev/null 2>&1; then
    python3 "$HERE/mpping.py" "$IP" "$PORT" 2 2>&1 | tee -a "$OUT"
fi
say ""

# --- 5. домен ----------------------------------------------------------------
say "[5] ДОМЕН"
if [ -n "$ARG" ] && [ "${ARG#--}" = "$ARG" ]; then
    say "    проверяю: $ARG"
    if command -v dig >/dev/null 2>&1; then
        say "    A-запись:      $(dig +short A "$ARG" | head -1)"
        say "    SRV _minecraft: $(dig +short SRV "_minecraft._tcp.$ARG" | head -3 | tr '\n' ' ')"
    else
        say "    A-запись:      $(getent hosts "$ARG" | awk '{ print $1; exit }')"
        say "    (dig нет, SRV не проверить)"
    fi
    if [ -n "$IP" ] && command -v dig >/dev/null 2>&1; then
        DIP=$(dig +short A "$ARG" | head -1)
        [ -n "$DIP" ] && [ "$DIP" != "$IP" ] && \
            say "    >>> домен указывает на $DIP, а сервер на $IP — вот и не пингуется"
    fi
    if command -v python3 >/dev/null 2>&1; then
        python3 "$HERE/mpping.py" "$ARG" "$PORT" 2 "$ARG" 2>&1 | tee -a "$OUT"
    fi
else
    say "    домен не указан. если заходишь через домен, повтори:"
    say "      bash $0 $DIR твой.домен"
fi
say ""

# --- 6. фаерволл -------------------------------------------------------------
say "[6] ФАЕРВОЛЛ"
if command -v ufw >/dev/null 2>&1; then
    say "    ufw: $(ufw status 2>/dev/null | head -1)"
    ufw status numbered 2>/dev/null | grep -E "$PORT|DENY|LIMIT" | head -6 | sed 's/^/    /' | tee -a "$OUT"
fi
if command -v iptables >/dev/null 2>&1; then
    say "    iptables (первые 8 правил):"
    iptables -S 2>/dev/null | head -8 | sed 's/^/    /' | tee -a "$OUT"
fi
if command -v fail2ban-client >/dev/null 2>&1; then
    say "    fail2ban: $(fail2ban-client status 2>/dev/null | grep -i 'jail list' | head -1)"
fi
say ""

# --- 7. ошибки в логе --------------------------------------------------------
say "[7] ОШИБКИ В ЛОГЕ (последние 2000 строк)"
LOG=$DIR/logs/latest.log
if [ -f "$LOG" ]; then
    for pat in 'OutOfMemoryError' 'direct buffer' 'Cannot reserve' 'Too many open files' \
               'Read timed out' 'Connection reset' 'Timed out' 'Address already in use' \
               'NoRouteToHost' 'failed to bind' 'Unable to bind'; do
        n=$(tail -2000 "$LOG" 2>/dev/null | grep -c -F "$pat" || true)
        [ "${n:-0}" -gt 0 ] && say "    $n × $pat"
    done
    say ""
    say "    последние 3 строки с ошибкой:"
    tail -2000 "$LOG" 2>/dev/null | grep -iE 'error|exception|warn' | tail -3 | cut -c1-160 | sed 's/^/      /' | tee -a "$OUT"
else
    say "    нет $LOG"
fi
say ""

# --- 8. флаги JVM ------------------------------------------------------------
say "[8] ФЛАГИ JVM"
if [ -f "$DIR/start.sh" ]; then
    grep -oE '\-XX:(MaxDirectMemorySize|MaxMetaspaceSize)=[0-9a-zA-Z]+' "$DIR/start.sh" | \
        sed 's/^/    /' | tee -a "$OUT" || true
    grep -q 'MaxDirectMemorySize' "$DIR/start.sh" && \
        say "    (если в логе OutOfMemoryError direct buffer — снять: bash $0 $DIR --revert-mem)"
else
    say "    нет start.sh"
fi
say ""
say "[9] ВЕРДИКТ"
OOM_DIRECT=$(tail -2000 "$LOG" 2>/dev/null | grep -c -E 'direct buffer|Cannot reserve' || true)
OOM_ANY=$(tail -2000 "$LOG" 2>/dev/null | grep -c 'OutOfMemoryError' || true)
if [ "${OOM_DIRECT:-0}" -gt 0 ]; then
    say "    В ЛОГЕ нехватка НАТИВНОЙ памяти (direct buffer). Netty не может выделить"
    say "    буфер под соединение -> пинг висит, вход идёт рывками."
    say "    Это следствие лимита -XX:MaxDirectMemorySize, который мы поставили."
    say "    Лечение одной командой:"
    say "      bash $0 $DIR --revert-mem"
    say "    потом обычный рестарт."
elif [ "${Q:-0}" -gt 5 ] 2>/dev/null; then
    say "    Очередь подключений забита -> это флуд или зависший accept."
    say "    Проверь: ss -tan state syn-recv | wc -l  и  tail -100 $LOG"
elif [ "${SYN:-0}" -gt 200 ] 2>/dev/null; then
    say "    Очень много полуоткрытых соединений (\$SYN) -> SYN-флуд."
    say "      sysctl -w net.ipv4.tcp_syncookies=1 net.core.somaxconn=4096"
elif [ "${LOCAL_OK:-0}" -ne 0 ]; then
    say "    Локальный пинг не проходит -> дело в самом сервере (порт/процесс/потоки)."
    say "    Смотри пункт 7 и: bash $0 $DIR --revert-mem"
else
    say "    Локально пинг отвечает нормально. Значит сервер живой, а проблема"
    say "    снаружи: DNS домена, фаерволл провайдера или прокси перед сервером."
    say "    Смотри пункты 4-6: совпадает ли IP домена с внешним IP машины."
fi
say ""
say "готово. Пришли $OUT"
