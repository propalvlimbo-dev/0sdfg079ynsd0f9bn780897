#!/usr/bin/env bash
# ============================================================================
#  lagdoctor — находит плагин, который съедает 35% времени медленных тиков
# ----------------------------------------------------------------------------
#  В профиле spark (только тики >= 80 мс) первое место занимают
#  oII.mloTI() / oII.mloOO() — обфусцированные классы в корневом пакете.
#  Spark не отнёс их ни к одному плагину, поэтому имя ищем по jar.
#
#  Запуск:  bash lagdoctor.sh            (отчёт: lag-report.txt)
# ============================================================================
set -u

cd "$(dirname "$0")" || exit 1
REPORT="lag-report.txt"
: > "$REPORT"

log() { printf '%s\n' "$*" | tee -a "$REPORT" >/dev/null; }
raw() { printf '%s\n' "$*" >> "$REPORT"; }

log "lagreport $(date '+%Y-%m-%d %H:%M:%S')"
log "каталог: $(pwd)"
log ""

# --- 1. поиск класса oII ----------------------------------------------------
log "== 1. Поиск oII / mloTI в plugins/*.jar =="
found=0
tmp="$(mktemp -d 2>/dev/null || echo /tmp/lagdoctor.$$)"
mkdir -p "$tmp"
trap 'rm -rf "$tmp"' EXIT

for j in plugins/*.jar; do
    [ -f "$j" ] || continue
    list="$(unzip -l "$j" 2>/dev/null | awk '{print $4}')"
    [ -n "$list" ] || continue

    if printf '%s\n' "$list" | grep -qE '(^|/)oII(\.class|/|\$)'; then
        log "  НАЙДЕН: $j"
        printf '%s\n' "$list" | grep -E '(^|/)oII' | head -5 | sed 's/^/     /' | while read -r l; do raw "$l"; done
        found=1
        continue
    fi

    # вложенные jar (shaded-библиотеки): не больше 12 штук на плагин
    inner_count="$(printf '%s\n' "$list" | grep -cE '\.jar$' || true)"
    [ "${inner_count:-0}" -gt 0 ] || continue
    [ "${inner_count:-0}" -le 200 ] || continue

    i=0
    for inner in $(printf '%s\n' "$list" | grep -E '\.jar$' | head -12); do
        i=$((i + 1))
        unzip -p "$j" "$inner" > "$tmp/i$i.jar" 2>/dev/null || continue
        if unzip -l "$tmp/i$i.jar" 2>/dev/null | awk '{print $4}' | grep -qE '(^|/)oII\.class$'; then
            log "  НАЙДЕН (вложенный): $j  ->  $inner"
            found=1
        fi
        rm -f "$tmp/i$i.jar"
    done
done
[ "$found" = "0" ] && log "  не найден ни в одном jar → класс создаётся в рантайме (прокси/ByteBuddy)"
log ""

# --- 2. список плагинов -----------------------------------------------------
log "== 2. Установленные плагины (имя + версия) =="
for j in plugins/*.jar; do
    [ -f "$j" ] || continue
    name="$(unzip -p "$j" plugin.yml 2>/dev/null | awk '/^name:/{print $2; exit}')"
    ver="$(unzip -p "$j" plugin.yml 2>/dev/null | awk '/^version:/{print $2; exit}')"
    if [ -n "${name:-}" ]; then
        log "  $name ${ver:-?}  ($j)"
    else
        log "  ???  ($j)"
    fi
done
log ""

# --- 3. окружение -----------------------------------------------------------
log "== 3. Запуск и память =="
pid=""
if command -v pgrep >/dev/null 2>&1; then
    pid="$(pgrep -f 'server\.jar|leaf-|paper-' 2>/dev/null | head -1)"
fi
if [ -n "${pid:-}" ] && [ -r "/proc/$pid/cmdline" ]; then
    log "  pid: $pid"
    log "  flags: $(tr '\0' ' ' < "/proc/$pid/cmdline" | cut -c1-700)"
    grep -E 'VmRSS|VmSwap' "/proc/$pid/status" 2>/dev/null | sed 's/^/  /' | while read -r l; do raw "$l"; done
else
    log "  процесс сервера не найден (запусти скрипт при работающем сервере или из его консоли)"
fi
free -m 2>/dev/null | sed 's/^/  /' | while read -r l; do raw "$l"; done
log ""

# --- 4. GC ------------------------------------------------------------------
log "== 4. GC-лог =="
if [ -f logs/gc.log ]; then
    grep -aE 'Pause Young|Pause Full|Pause Remark' logs/gc.log 2>/dev/null | tail -12 | sed 's/^/  /' | while read -r l; do raw "$l"; done
    log "  (строк в GC-логе: $(wc -l < logs/gc.log))"
else
    log "  logs/gc.log нет — GC-лог не включён"
fi
log ""

# --- 5. подозрительное в логе ----------------------------------------------
log "== 5. Подозрительное в latest.log =="
if [ -f logs/latest.log ]; then
    grep -aE "Can't keep up|Overloaded|Exception|ERROR" logs/latest.log 2>/dev/null \
        | tail -25 | sed 's/^/  /' | while read -r l; do raw "$l"; done
else
    log "  logs/latest.log нет"
fi
log ""

log "== 6. Как читать =="
log "  * есть имя jar в п.1 — это и есть плагин из 35%: пришли отчёт,"
log "    и я скажу, что в нём менять (обычно period 1 -> 20 тиков);"
log "  * п.1 пуст — виновника ищем бисекцией: отключить половину плагинов,"
log "    перезапуск, сравнить MSPT, сузить."

echo
echo "Готово: $(pwd)/$REPORT"
echo "Пришли этот файл — в нём плагин, текущие флаги JVM и состояние GC."
