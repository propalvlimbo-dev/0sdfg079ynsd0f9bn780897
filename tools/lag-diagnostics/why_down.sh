#!/usr/bin/env bash
# =============================================================================
#  why_down.sh — «сервер выключился и выкинуло всех»: одна команда, чтобы
#                точно узнать причину и сразу включить автовозврат сервера.
#
#  Запуск (на VDS, из любой папки):
#      bash why_down.sh [путь/к/папке/сервера]
#   или одной строкой прямо с GitHub:
#      curl -fsSL <RAW>/tools/lag-diagnostics/why_down.sh | bash
#
#  Что делает:
#   1. сам находит папку сервера (аргумент, /root/RW_GRIEF, текущая папка…);
#   2. по latest.log, crash-reports и dmesg ОПРЕДЕЛЯЕТ причину остановки
#      (OOM-киллер / нехватка heap / watchdog / непойманное исключение /
#      чистая остановка stop / ручной kill) и печатает виновника-плагин;
#   3. показывает память: сколько всего, сколько реально съел java, какой -Xmx;
#   4. ПРИМЕНЯЕТ единственное безопасное исправление: правит start.sh так,
#      чтобы сервер ВСЕГДА поднимался обратно, даже после «чистого» stop
#      (сейчас цикл делает break на коде 0 — из-за этого сервер остаётся
#      лежать выключенным). Для осознанной остановки: touch .nostart
#
#  Скрипт ТОЛЬКО читает логи и правит start.sh. Он НЕ трогает плагины,
#  НЕ трогает порты :8085 / :20559 / :24454 и ничего не удаляет.
# =============================================================================
set -u

say()  { printf '%s\n' "$*"; }
head1() { printf '\n\033[1m=== %s ===\033[0m\n' "$*"; }

# --- 1. Где сервер? ---------------------------------------------------------
DIR="${1:-}"
[ -n "$DIR" ] || for c in /root/RW_GRIEF /root/mc /home/mc "$PWD"; do
    [ -f "$c/start.sh" ] || [ -f "$c/logs/latest.log" ] || [ -f "$c/server.jar" ] && DIR="$c" && break
done
[ -n "$DIR" ] && [ -d "$DIR" ] || DIR="$PWD"
cd "$DIR" || exit 1

head1 "СЕРВЕР: $DIR"

LOG=""
for f in logs/latest.log logs/server.log server.log; do
    [ -f "$f" ] && LOG="$f" && break
done
if [ -z "$LOG" ]; then
    say "НЕ НАЙДЕН лог (logs/latest.log). Скрипт должен лежать/запускаться в папке сервера."
    say "Подсказка: bash why_down.sh /root/RW_GRIEF"
    exit 1
fi
say "лог: $LOG ($(wc -l < "$LOG") строк, изменён $(date -r "$LOG" '+%F %T'))"

# --- 2. Жив ли сервер сейчас ------------------------------------------------
PID=$(pgrep -f 'java .*-jar .*nogui' | head -1)
if [ -n "${PID:-}" ]; then
    say "сейчас: java ЗАПУЩЕН (pid $PID, RSS $(awk '/VmRSS/{print $2" "$3}' /proc/$PID/status 2>/dev/null))"
else
    say "сейчас: java НЕ запущен (сервер лежит)"
fi

# --- 3. Чем закончился лог --------------------------------------------------
head1 "ПОСЛЕДНИЕ 25 СТРОК ЛОГА"
tail -n 25 "$LOG"

# --- 4. Причина: от частого к редкому --------------------------------------
VERDICT=""
WHY=""

# 4.1. OOM-киллер ядра (лог обрывается без «Stopping server»)
if ! tail -n 200 "$LOG" | grep -qi 'Stopping server\|Stopping the server\|Shutting down'; then
    if command -v dmesg >/dev/null 2>&1; then
        OOM=$(dmesg -T 2>/dev/null | grep -iE 'killed process|out of memory' | tail -n 3)
    fi
    [ -z "${OOM:-}" ] && [ -r /var/log/kern.log ] &&
        OOM=$(grep -iE 'killed process|out of memory' /var/log/kern.log 2>/dev/null | tail -n 3)
    [ -z "${OOM:-}" ] && command -v journalctl >/dev/null 2>&1 &&
        OOM=$(journalctl -k --since '6 hours ago' --no-pager 2>/dev/null |
              grep -iE 'killed process|out of memory' | tail -n 3)
    if [ -n "${OOM:-}" ]; then
        VERDICT="OOM-KILLER (ядро убило java — серверу не хватило оперативной памяти)"
        WHY="Лог обрывается без 'Stopping server' + в ядре видно убийство процесса.
     Лечение: снизить -Xmx в start.sh (сейчас $(grep -oE '\-Xmx[0-9]+[MG]' start.sh 2>/dev/null | head -1))
     или добавить swap. Ниже — сколько памяти реально съедал java."
        say ""
        head1 "ЯДРО (OOM)"
        say "$OOM"
    else
        VERDICT="РЕЗКАЯ СМЕРТЬ без сообщения об остановке (java убит сигналом/вылетел, лог обрывается)"
        WHY="В конце лога нет 'Stopping server'. Это SIGKILL от OOM-киллера, падение JVM
     или kill извне. Смотри блок ПАМЯТЬ ниже и crash-reports/."
    fi
fi

# 4.2. Нехватка heap
if grep -q 'OutOfMemoryError' "$LOG"; then
    VERDICT="HEAP OOM (java сам написал OutOfMemoryError)"
    OOMN=$(grep -c 'OutOfMemoryError' "$LOG")
    WHY="OutOfMemoryError в логе: $OMN шт. Последний:
     $(grep 'OutOfMemoryError' "$LOG" | tail -1 | cut -c1-200)
     Лечение: поднять swap / снизить -Xmx / найти плагин-утечку (ищи в стектрейсе выше)."
    head1 "OutOfMemoryError (последние 3)"
    grep -n 'OutOfMemoryError' "$LOG" | tail -n 3 | cut -c1-220
fi

# 4.3. Watchdog Paper
if grep -q 'DO NOT REPORT THIS TO PAPER\|--- Watchdog\|A single server tick took' "$LOG"; then
    VERDICT="WATCHDOG (главный поток завис >60 с — Paper принудительно убил сервер)"
    WHY="Сервер встал в глухой фриз, Paper спас мир от вечного зависания и остановился.
     Это НЕ античит. Надо искать, что подвесило главный поток: долгий синхронный
     запрос к БД/сайту (FloriumAC — облачный!), генерация чанков, огромный /rtp."
    head1 "WATCHDOG"
    grep -A6 'DO NOT REPORT THIS TO PAPER' "$LOG" | tail -n 12 | cut -c1-220
    grep -n 'A single server tick took' "$LOG" | tail -n 3 | cut -c1-220
fi

# 4.4. Непойманное исключение в тике — Paper останавливает сервер
if grep -q 'Encountered an unexpected exception' "$LOG"; then
    VERDICT="НЕПОЙМАННОЕ ИСКЛЮЧЕНИЕ в главном цикле — Paper остановил сервер"
    WHY="Исключение вылетело наружу из тика, сервер штатно рухнул.
     Ниже — стектрейс и плагин-виновник."
    head1 "CRASH (Encountered an unexpected exception)"
    grep -A25 'Encountered an unexpected exception' "$LOG" | tail -n 26 | cut -c1-220
fi

# 4.5. Чистая остановка: ищем, КТО её вызвал
if [ -z "$VERDICT" ] && grep -qi 'Stopping server\|Stopping the server\|Running shutdown' "$LOG"; then
    VERDICT="ЧИСТАЯ ОСТАНОВКА (кто-то выполнил stop)"
    TRIG=$(grep -iE 'issued server command: /(stop|restart|rl)|(CONSOLE|Server) issued server command' "$LOG" | tail -n 3)
    if [ -n "$TRIG" ]; then
        WHY="Остановку вызвала команда (последние совпадения ниже). Если это /restart от плагина
     или CONSOLE — ищи плагин авторестарта (AutoRestart, ServerUtils, PlugMan, панель)."
        head1 "КТО ОСТАНОВИЛ"
        say "$TRIG" | cut -c1-220
    else
        WHY="'Stopping server' есть, но команды stop в логе нет — значит stop пришёл НЕ из чата:
     плагин вызвал Bukkit.shutdown()/Server.shutdown(), сработал авторестарт,
     или панель/скрипт отправил stop в консоль."
    fi
    head1 "СТРОКИ ПЕРЕД ОСТАНОВКОЙ"
    grep -n -i -B8 'Stopping server' "$LOG" | tail -n 12 | cut -c1-220
fi

# 4.6. crash-reports за сутки
if [ -d crash-reports ]; then
    NEW=$(find crash-reports -name 'crash-*.txt' -mmin -1440 2>/dev/null | sort | tail -n 3)
    if [ -n "$NEW" ]; then
        head1 "CRASH-REPORTS ЗА СУТКИ"
        for f in $NEW; do
            say "--- $f ($(date -r "$f" '+%F %T'))"
            sed -n '1,12p' "$f" | cut -c1-200
        done
    fi
fi

# --- 5. Память: сколько всего / сколько съел java / какой -Xmx ---------------
head1 "ПАМЯТЬ"
free -m 2>/dev/null | sed 's/^/  /'
say ""
XMX=$(grep -oE '\-Xmx[0-9]+[MG]' start.sh 2>/dev/null | head -1)
if [ -z "$XMX" ]; then
    XMX=$(grep -oE '\-Xmx\$\{?[A-Z_]+\}?' start.sh 2>/dev/null | head -1)
    if [ -n "$XMX" ]; then
        XMX="$XMX  (считается от RAM: $(grep -oE 'HEAP_MAX="?[0-9]+[MG]"?' start.sh 2>/dev/null | tr '\n' ' '))"
    fi
fi
DIRM=$(grep -oE 'MaxDirectMemorySize=[0-9]+[MG]' start.sh 2>/dev/null | head -1)
say "  в start.sh: ${XMX:-не найден}  ${DIRM:-}"
CUR=$(pgrep -f 'java .*-jar .*nogui' | head -1)
if [ -n "${CUR:-}" ]; then
    say "  java сейчас: pid $CUR, RSS $(awk '/VmRSS/{printf "%.0f МБ", $2/1024}' /proc/$CUR/status 2>/dev/null)"
else
    say "  java сейчас не запущен — сравнить не с чем."
    say "  ВАЖНО: если в start.sh $(echo ${XMX:-}) близко к объёму RAM выше — это и есть причина"
    say "  OOM-киллера: heap + DirectMemory + Metaspace + MySQL + ОС должны влезать в RAM."
fi
SW=$(swapon --show=NAME,SIZE --noheadings 2>/dev/null | tr '\n' ' ')
say "  swap: ${SW:-НЕТ (при OOM-киллере первым делом добавь swap)}"

# --- 6. ИТОГ ----------------------------------------------------------------
head1 "ИТОГ"
if [ -n "$VERDICT" ]; then
    say "ПРИЧИНА: $VERDICT"
    say "$WHY"
else
    say "ПРИЧИНА: в логе нет ни аварийного выхода, ни 'Stopping server'."
    say "  Скорее всего java был убит снаружи (kill, перезагрузка VDS, панель хостинга)"
    say "  или latest.log успел перезаписаться. Проверь logs/*.log.gz и историю перезапусков ниже."
fi

# --- 7. История перезапусков (если start.sh уже patched) --------------------
if [ -f logs/restarts.log ]; then
    head1 "ПОСЛЕДНИЕ ПЕРЕЗАПУСКИ (logs/restarts.log)"
    tail -n 15 logs/restarts.log
fi

# --- 8. АВТОФИКС: сервер всегда должен подниматься обратно ------------------
head1 "АВТОФИКС start.sh (сервер больше не будет лежать выключенным)"
if [ -f start.sh ]; then
    if grep -q 'CODE" -eq 0 \] && \[ -f .nostart' start.sh; then
        say "  УЖЕ ОК: start.sh сам поднимает сервер после любой остановки."
        say "  (чтобы остановить сервер навсегда: touch $DIR/.nostart , затем stop)"
    else
        cp -f start.sh "start.sh.bak.$(date +%s)"
        python3 - <<'PY' 2>/dev/null || perl -0pi -e 's/\[ "\$CODE" -eq 0 \] && echo "\[Elytrix\] Штатная остановка \(stop\)\." && break/printf "%s\\n" "[Elytrix] Код выхода $CODE."/ if 0; s/\[ "\$CODE" -eq 0 \] && echo "\[Elytrix\] Штатная остановка \(stop\)\." && break/if [ "$CODE" -eq 0 ] \&\& [ -f .nostart ]; then rm -f .nostart; echo "[Elytrix] Штатная остановка (.nostart)."; break; fi/'
import re, pathlib
p = pathlib.Path('start.sh'); s = p.read_text(encoding='utf-8')
old = '[ "$CODE" -eq 0 ] && echo "[Elytrix] Штатная остановка (stop)." && break'
if old in s:
    note = ''
    if 'Автовозврат' not in s:
        note = ('# Автовозврат: на ЛЮБОМ коде выхода поднимаем сервер обратно,\n'
                '    # в том числе после «чистого» stop (раньше цикл делал break на коде 0,\n'
                '    # и сервер оставался лежать выключенным).\n'
                '    # Чтобы остановить НАВСЕГДА: touch .nostart\n'
                '    ')
    new = (note + 'if [ "$CODE" -eq 0 ] && [ -f .nostart ]; then\n'
           '        rm -f .nostart\n'
           '        echo "[Elytrix] Штатная остановка (.nostart)." && break\n'
           '    fi')
    s = s.replace(old, new, 1)
s = s.replace('mkdir -p logs', 'mkdir -p logs\n'
              'rm -f .nostart\n'
              'echo "[Elytrix] $(date \'+%F %T\') START" >> logs/restarts.log', 1)
if 'exit code $CODE" >> logs/restarts.log' not in s:
    s = s.replace('CODE=$?', 'CODE=$?\n    echo "[Elytrix] $(date \'+%F %T\') exit code $CODE" >> logs/restarts.log', 1)
p.write_text(s, encoding='utf-8')
print('  python: start.sh пропатчен')
PY
        if bash -n start.sh 2>/dev/null; then
            say "  ГОТОВО: start.sh теперь поднимает сервер при ЛЮБОМ коде выхода."
            say "  Бэкап старого: start.sh.bak.*"
            say "  Чтобы остановить НАВСЕГДА: touch $DIR/.nostart   (затем stop)"
            say "  История перезапусков: $DIR/logs/restarts.log"
            say ""
            say "  ВНИМАНИЕ: новый start.sh начнёт действовать, когда перезапустится сам"
            say "  wrapper (start.sh). Сам java перезапускать не надо."
        else
            say "  ОШИБКА: патч не прошёл проверку синтаксиса — восстанови из start.sh.bak.*"
        fi
    fi
else
    say "  start.sh не найден в $DIR — автовозврат настроить не удалось."
fi

head1 "ЧТО ДАЛЬШЕ"
say "  1) Если java сейчас НЕ запущен — подними сервер тем же способом, что и обычно:"
say "       screen -dmS mc bash $DIR/start.sh      (или как ты его запускаешь)"
say "  2) Прогони этот скрипт ещё раз после следующего падения — он покажет"
say "     уже точную причину и историю кодов выхода."
say "  3) Пришли мне вывод — я скажу, какой плагин выгружать."
