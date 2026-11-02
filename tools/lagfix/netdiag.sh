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
    say "[DNS] $DOMAIN"
    if command -v dig >/dev/null 2>&1; then
        A=$(dig +short A "$DOMAIN" 2>/dev/null | head -1)
        AAAA=$(dig +short AAAA "$DOMAIN" 2>/dev/null | head -1)
        SRV=$(dig +short SRV "_minecraft._tcp.$DOMAIN" 2>/dev/null | head -2)
        NS=$(dig +short NS "$DOMAIN" 2>/dev/null | head -3)
        say "  A-запись:      ${A:-НЕТ}"
        say "  AAAA-запись:   ${AAAA:-нет}"
        say "  SRV _minecraft: ${SRV:-нет}"
        say "  NS серверы:    $(printf '%s' "$NS" | tr '\n' ' ')"
        if [ -n "$AAAA" ]; then
            say "  >>> ЕСТЬ AAAA (IPv6). Если у машины нет рабочего IPv6, клиент сначала"
            say "      идёт по IPv6, ждёт таймаут и только потом пробует IPv4 —"
            say "      это и есть 'долго пингуется'. Убери AAAA в панели домена."
        fi
        if [ -n "$SRV" ]; then
            say "  >>> ЕСТЬ SRV-запись. Клиент предпочитает её A-записи: если она ведёт"
            say "      на старый адрес/порт, домен не работает, а IP работает."
            say "      Проверь строку выше: адрес должен быть $IP, порт 25565."
        fi
        if [ -n "$A" ] && [ -n "$IP" ] && [ "$A" != "$IP" ]; then
            say "  >>> A указывает на $A, а машина на $IP — домен не туда."
        fi
        [ -n "$A" ] && [ "$A" = "$IP" ] && say "  A совпадает с внешним IP — хорошо"
    else
        say "  dig не установлен, показываю getent:"
        say "  $(getent hosts "$DOMAIN" 2>/dev/null | tr '\n' ' ')"
        say "  (для проверки AAAA/SRV поставь dnsutils: apt install -y dnsutils)"
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
