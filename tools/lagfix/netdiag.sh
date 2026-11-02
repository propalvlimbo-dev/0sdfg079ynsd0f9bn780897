#!/usr/bin/env bash
# netdiag.sh — почему домен не пингуется, а по IP «очень долго».
# Проверяет ровно три подозреваемых: DNS (A/AAAA/SRV), сам прокси на 25565
# и его связку с игровым сервером на 25566.
#
#   bash netdiag.sh /root/RW_GRIEF твой.домен
#   bash netdiag.sh /root/RW_GRIEF            # без домена, только IP-часть
set -u
export LC_ALL=C

DIR=${1:-}
DOMAIN=${2:-}
[ -n "$DIR" ] || { echo "использование: bash $0 <папка_сервера> [домен]" >&2; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$DIR/netdiag.txt
say() { printf '%s\n' "$*" | tee -a "$OUT"; }
q()   { printf '%s\n' "$*" | tee -a "$OUT"; }
digq() {  # $1 = тип, $2 = имя, $3 = сервер (необязательно)
    local t=$1 n=$2 srv=${3:-}
    if [ -n "$srv" ]; then
        timeout 4 dig +short +tries=1 +time=2 @"$srv" "$t" "$n" 2>/dev/null
    else
        timeout 4 dig +short +tries=1 +time=2 "$t" "$n" 2>/dev/null
    fi | grep -vE '^;|communications error|timed out|status:' | sed '/^$/d' | head -3
}
dns_ok() {  # 0 = локальный резолвер жив и правда отдаёт адрес
    timeout 3 dig +short +tries=1 +time=2 A example.com 2>/dev/null | grep -qE '^[0-9]{1,3}(\.[0-9]{1,3}){3}$'
}

: > "$OUT"
say "=== netdiag ($(date '+%Y-%m-%d %H:%M:%S')) ==="
say ""

# --- внешний IP --------------------------------------------------------------
IP=$(curl -s --max-time 6 https://api.ipify.org 2>/dev/null || true)
[ -z "$IP" ] && IP=$(curl -s --max-time 6 https://ifconfig.me 2>/dev/null || true)
[ -z "$IP" ] && IP=$(hostname -I 2>/dev/null | awk '{ print $1 }')
say "внешний IP машины: ${IP:-не определился}"

# --- DNS ---------------------------------------------------------------------
if [ -n "$DOMAIN" ]; then
    say ""
    say "[DNS] локальный резолвер"
    RESOLV=$(awk '/^nameserver/ { printf "%s ", $2 }' /etc/resolv.conf 2>/dev/null)
    say "  /etc/resolv.conf: ${RESOLV:-пусто}"
    if command -v resolvectl >/dev/null 2>&1; then
        say "  systemd-resolved: $(systemctl is-active systemd-resolved 2>/dev/null || echo '?')"
    fi
    if dns_ok; then
        say "  локальный резолвер отвечает"
        STUB=ok
    else
        STUB=dead
        say "  >>> ЛОКАЛЬНЫЙ RESOLVER НЕ ОТВЕЧАЕТ (127.0.0.53)."
        say "      Машина не может разрешать имена: любой сервис, который ходит по"
        say "      домену, будет ждать таймаут на каждое обращение."
        say "      Лечение:"
        say "        systemctl restart systemd-resolved"
        say "        printf 'nameserver 1.1.1.1\\nnameserver 8.8.8.8\\n' > /etc/resolv.conf"
        say "      Проверка: dig +short A example.com"
    fi

    say ""
    say "[DNS] $DOMAIN"
    A=$(digq A "$DOMAIN"); AAAA=$(digq AAAA "$DOMAIN")
    SRV=$(digq SRV "_minecraft._tcp.$DOMAIN")
    NS=$(digq NS "$DOMAIN" | tr '\n' ' ')
    A_PUB=$(digq A "$DOMAIN" 1.1.1.1); AAAA_PUB=$(digq AAAA "$DOMAIN" 1.1.1.1)
    SRV_PUB=$(digq SRV "_minecraft._tcp.$DOMAIN" 1.1.1.1)

    # только настоящие IPv4/IPv6, иначе "нет"
    A=$(printf '%s\n' "$A" | grep -E '^[0-9]{1,3}(\.[0-9]{1,3}){3}$' | head -1)
    AAAA=$(printf '%s\n' "$AAAA" | grep -E '^[0-9a-fA-F:]+$' | head -1)
    A_PUB=$(printf '%s\n' "$A_PUB" | grep -E '^[0-9]{1,3}(\.[0-9]{1,3}){3}$' | head -1)
    AAAA_PUB=$(printf '%s\n' "$AAAA_PUB" | grep -E '^[0-9a-fA-F:]+$' | head -1)

    say "  A:             ${A:-нет ответа}"
    say "  AAAA:          ${AAAA:-нет}"
    say "  SRV _minecraft: ${SRV:-нет}"
    say "  NS:            ${NS:-нет ответа}"
    if [ -n "$A_PUB" ] || [ -n "$AAA_PUB" ] || [ -n "$SRV_PUB" ]; then
        say "  через 1.1.1.1: A=${A_PUB:-нет} AAAA=${AAAA_PUB:-нет} SRV=$(printf '%s' "$SRV_PUB" | tr '\n' ' ' | sed 's/ *$//')"
    fi
    say ""

    A_EFF=${A:-$A_PUB}; AAAA_EFF=${AAAA:-$AAAA_PUB}; SRV_EFF=${SRV:-$SRV_PUB}
    echo ""
    if [ "$STUB" = dead ]; then
        if [ -n "$A_EFF" ]; then
            say "  ВЫВОД: домен настроен верно (виден через 1.1.1.1: $A_EFF),"
            say "         сломан только резолвер этой машины — им и чинится."
        else
            say "  ВЫВОД: резолвер машины мёртв И домен не виден публично — правь и то, и то."
        fi
    elif [ -z "$A_EFF" ]; then
        say "  ВЫВОД: A-записи нет — домен не настроен на этот сервер."
    fi
    [ -n "$AAAA_EFF" ] && say "  >>> есть AAAA ($AAAA_EFF): клиенты без IPv6 сначала ждут таймаут. Убери AAAA в панели домена."
    [ -n "$A_EFF" ] && [ -n "$IP" ] && [ "$A_EFF" != "$IP" ] && say "  >>> A=$A_EFF, а машина $IP — домен не туда."
    [ -n "$A_EFF" ] && [ "$A_EFF" = "$IP" ] && say "  A совпадает с внешним IP — хорошо"
    if [ -n "$SRV_EFF" ]; then
        say "  >>> есть SRV ($SRV_EFF): клиент предпочитает её A-записи."
        case "$SRV_EFF" in
            *"$IP"*) say "      адрес верный" ;;
            *) say "      адрес НЕ $IP — вот почему домен не работает, а IP работает." ;;
        esac
    fi
fi

# --- пинг прокси и бэкенда ---------------------------------------------------
say ""
say "[ПИНГ] замеряю по 5 раз: не «на глаз», а в миллисекундах"
for pp in "прокси 25565:25565" "сервер 25566:25566"; do
    label=${pp%%:*}; port=${pp##*:}
    say "  $label"
    if command -v python3 >/dev/null 2>&1 && [ -f "$HERE/mpping.py" ]; then
        python3 "$HERE/mpping.py" 127.0.0.1 "$port" 5 2>&1 | sed 's/^/    /' | tee -a "$OUT"
    else
        say "    нет python3 — пропускаю"
    fi
done

if [ -n "$DOMAIN" ] && command -v python3 >/dev/null 2>&1; then
    say "  через домен $DOMAIN"
    python3 "$HERE/mpping.py" "$DOMAIN" 25565 3 "$DOMAIN" 2>&1 | sed 's/^/    /' | tee -a "$OUT"
fi
if [ -n "$IP" ] && command -v python3 >/dev/null 2>&1; then
    say "  по IP $IP:25565 (как заходят игроки без домена)"
    python3 "$HERE/mpping.py" "$IP" 25565 3 2>&1 | sed 's/^/    /' | tee -a "$OUT"
fi

# --- кто на портах -----------------------------------------------------------
say ""
say "[ПРОЦЕССЫ] кто слушает 25565 и 25566"
if command -v ss >/dev/null 2>&1; then
    ss -ltnp 2>/dev/null | grep -E ':25565|:25566' | sed 's/^/  /' | tee -a "$OUT"
    say "  установленных соединений на 25565: $(ss -tan state established 2>/dev/null | awk '$4 ~ /:25565$/' | wc -l)"
    say "  полуоткрытых SYN-RECV:            $(ss -tan state syn-recv 2>/dev/null | tail -n +2 | wc -l)"
fi

# --- конфиг прокси -----------------------------------------------------------
say ""
say "[ПРОКСИ] настройки, от которых зависит скорость пинга"
CFG=""
for f in "$DIR/../proxy/velocity.toml" "$DIR/proxy/velocity.toml" /root/proxy/velocity.toml \
         /root/velocity/velocity.toml /root/NullCordX/velocity.toml "$DIR/velocity.toml"; do
    [ -f "$f" ] && { CFG=$f; break; }
done
if [ -n "$CFG" ]; then
    say "  конфиг: $CFG"
    grep -nE '^(bind|ping-passthrough|online-mode|forwarding-mode|motd|player-info-forwarding)' "$CFG" 2>/dev/null | head -12 | sed 's/^/    /' | tee -a "$OUT"
    say "    серверы:"
    awk '
        /^\[/ { insec = ($0 ~ /^\[servers\]/); next }
        insec && /=/ { print "      " $0 }
    ' "$CFG" | head -6 | tee -a "$OUT"
    say ""
    say "    адреса серверов в [servers]:"
    NAMED=0
    awk '
        /^\[/ { insec = ($0 ~ /^\[servers\]/); next }
        insec && /=/ {
            line = $0
            sub(/#.*/, "", line)
            split(line, kv, "=")
            name = kv[1]; val = kv[2]
            gsub(/^[ \t]+|[ \t]+$/, "", name)
            gsub(/^[ \t]+|[ \t]+$/, "", val)
            gsub(/"/, "", val)
            host = val; sub(/:[0-9]+$/, "", host)
            is_ip = (host ~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ || host == "localhost")
            printf "      %-12s %-24s %s\n", name, val, (is_ip ? "ip" : "ИМЯ -> нужен DNS")
            if (!is_ip) named++
        }
        END { exit (named > 0 ? 0 : 1) }
    ' "$CFG" | tee -a "$OUT"
    if awk '
        /^\[/ { insec = ($0 ~ /^\[servers\]/); next }
        insec && /=/ { line = $0; sub(/#.*/, "", line); split(line, kv, "="); val = kv[2];
                       gsub(/^[ \t]+|[ \t]+|"/, "", val); host = val; sub(/:[0-9]+$/, "", host);
                       if (host !~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ && host != "localhost") found = 1 }
        END { exit (found ? 0 : 1) }' "$CFG"; then
        say ""
        say "    >>> в [servers] указаны ИМЕНА, а не IP. Прокси разрешает их при каждом"
        say "        подключении и каждом пинге. Если DNS на машине лежит (а он лежит),"
        say "        каждое подключение ждёт таймаут — ровно твоя картина."
        say "        Замени адрес на 127.0.0.1:25566 — прокси и сервер на одной машине,"
        say "        DNS для этого не нужен вообще."
    fi
    PT=$(awk -F= '/^ping-passthrough/ { gsub(/[ "]/, "", $2); print $2 }' "$CFG" 2>/dev/null)
    case "${PT:-}" in
        ALL|MODS|DESCRIPTION)
            say ""
            say "  >>> ping-passthrough = $PT: прокси на КАЖДЫЙ пинг ходит к игровому серверу."
            say "      Если бэкенд отвечает медленно, пинг висит столько же. Поставь"
            say "      ping-passthrough = \"DISABLED\" и перезапусти прокси — пинг станет"
            say "      мгновенным (в списке будет MOTD прокси, а не сервера)."
            ;;
        DISABLED) say "    ping-passthrough=DISABLED — пинг не зависит от бэкенда, хорошо" ;;
    esac
else
    say "  velocity.toml не нашёл. где лежит прокси?"
    say "  посмотри: ls -l /proc/\$(pgrep -f NullCordX | head -1)/cwd"
fi

# --- утечка/GC прокси --------------------------------------------------------
PPID_=$(pgrep -f 'NullCordX' 2>/dev/null | head -1)
if [ -n "${PPID_:-}" ]; then
    say ""
    say "[ПРОКСИ] состояние JVM (pid $PPID_): $(ps -o etime= -p "$PPID_" | tr -d ' ') работы"
    JSTAT=""
    for c in jstat; do command -v "$c" >/dev/null 2>&1 && JSTAT=$c; done
    if [ -n "$JSTAT" ]; then
        "$JSTAT" -gcutil "$PPID_" 2>/dev/null | sed 's/^/  /' | tee -a "$OUT"
        say "  (если O — 100% и FGC растёт, прокси в GC-шторме: пинг будет рваный)"
    fi
    say "  RSS: $(awk '/^VmRSS:/ { print int($2 / 1024) " МБ" }' "/proc/$PPID_/status" 2>/dev/null)"
fi

# --- логи --------------------------------------------------------------------
say ""
say "[ЛОГИ] ошибки прокси и сервера"
for L in /root/proxy/logs/latest.log /root/velocity/logs/latest.log /root/NullCordX/logs/latest.log "$DIR/logs/latest.log"; do
    [ -f "$L" ] || continue
    say "  $L"
    for pat in 'OutOfMemory' 'timed out' 'Timed out' 'refused' 'No route' 'Closing' 'disconnect' 'rate limit' 'Too many'; do
        n=$(tail -500 "$L" 2>/dev/null | grep -c -F "$pat" || true)
        [ "${n:-0}" -gt 0 ] && say "    $n × $pat"
    done
done
say ""
say "готово. Пришли $OUT"
