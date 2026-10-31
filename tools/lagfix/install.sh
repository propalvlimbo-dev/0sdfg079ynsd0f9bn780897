#!/usr/bin/env bash
# ============================================================================
#  Elytrix — lagfix v1
# ----------------------------------------------------------------------------
#  Что делает (всё с бэкапами, повторный запуск безопасен):
#
#   1. start.sh:  -Dblib.server.version=1.21.10  — BLib 1.7.2 (последний релиз)
#      знает версии только до 1.21.10 и на 1.21.11 падает в Version.<clinit>
#      с UnsupportedVersionException; из-за него не включаются BCases, BMenu
#      и VirtualEntityApi. Свойство — штатный обход из самой библиотеки.
#
#   2. start.sh:  GC_MODE по умолчанию zgc. Профиль spark показал 19 young-GC
#      за ~50 секунд, средняя пауза 41 мс, каждые ~2.6 с, при аллокации
#      250 МБ/с. ZGC generational убирает эти паузы (<1 мс). Откат —
#      GC_MODE=g1 в start.sh или в окружении.
#
#   3. server.properties: sync-chunk-writes=false — сервер не ждёт fsync на
#      каждой записи чанка. Рекомендация Paper, снижает I/O-стопы (в профиле
#      CPU (system) 42-55%).
#
#   4. Кладёт lagdoctor.sh — он находит плагин с обфусцированным классом oII
#      (35.5% времени медленных тиков в профиле) и собирает отчёт.
#
#  Использование:
#      bash install.sh /root/RW_GRIEF
#      DISTANCE_TUNING=1 bash install.sh /root/RW_GRIEF   # + view/sim distance
#      NO_ZGC=1 bash install.sh /root/RW_GRIEF            # не трогать GC
# ============================================================================
set -eu

SRV="${1:-/root/RW_GRIEF}"
ZGC="${NO_ZGC:-0}"
DISTANCE_TUNING="${DISTANCE_TUNING:-0}"
STAMP="$(date +%Y%m%d-%H%M%S)"

say()  { printf '[lagfix] %s\n' "$*"; }
warn() { printf '[lagfix] ВНИМАНИЕ: %s\n' "$*" >&2; }
die()  { printf '[lagfix] ОШИБКА: %s\n' "$*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
[ -d "$SRV" ] || die "каталог сервера не найден: $SRV"
cd "$SRV"
say "сервер: $(pwd)"

backup() {
    if [ ! -f "$1" ]; then return 0; fi
    if [ -f "$1.bak-lagfix-$STAMP" ]; then return 0; fi
    cp -a "$1" "$1.bak-lagfix-$STAMP"
}

# --- 1. BLib ----------------------------------------------------------------
if [ -f start.sh ]; then
    backup start.sh
    if grep -q 'blib.server.version' start.sh; then
        say "BLib: обход уже прописан, пропускаю"
    elif grep -q 'Dlog4j2.formatMsgNoLookups=true' start.sh; then
        sed -i 's/-Dlog4j2.formatMsgNoLookups=true/-Dlog4j2.formatMsgNoLookups=true -Dblib.server.version=1.21.10/' start.sh
        say "BLib: добавлен -Dblib.server.version=1.21.10"
    else
        sed -i 's/^\([[:space:]]*\)-Dfile.encoding=UTF-8/\1-Dfile.encoding=UTF-8\n\1-Dblib.server.version=1.21.10/' start.sh
        say "BLib: добавлен -Dblib.server.version=1.21.10"
    fi
    bash -n start.sh || die "start.sh перестал быть валидным bash — верни start.sh.bak-lagfix-$STAMP"
else
    warn "start.sh не найден — BLib и GC не тронуты"
fi

# --- 2. GC ------------------------------------------------------------------
if [ "$ZGC" != "1" ] && [ -f start.sh ]; then
    if grep -q 'GC_MODE:-g1' start.sh; then
        sed -i 's/GC_MODE:-g1/GC_MODE:-zgc/' start.sh
        say "GC: по умолчанию теперь zgc (откат: GC_MODE=g1)"
    elif grep -q 'GC_MODE:-zgc' start.sh; then
        say "GC: zgc уже включён"
    else
        warn "GC_MODE не найден в start.sh — GC оставлен как есть"
    fi
fi

# --- 3. server.properties ---------------------------------------------------
if [ -f server.properties ]; then
    backup server.properties
    set_prop() {
        key="$1"; val="$2"
        if grep -q "^${key}=" server.properties; then
            sed -i "s/^${key}=.*/${key}=${val}/" server.properties
        else
            printf '%s=%s\n' "$key" "$val" >> server.properties
        fi
    }
    set_prop sync-chunk-writes false
    say "server.properties: sync-chunk-writes=false"

    if [ "$DISTANCE_TUNING" = "1" ]; then
        vd="$(grep -E '^view-distance=' server.properties | cut -d= -f2 | tr -dc '0-9')"
        sd="$(grep -E '^simulation-distance=' server.properties | cut -d= -f2 | tr -dc '0-9')"
        if [ -n "$vd" ] && [ "$vd" -gt 8 ]; then set_prop view-distance 8; say "view-distance: $vd -> 8"; fi
        if [ -n "$sd" ] && [ "$sd" -gt 6 ]; then set_prop simulation-distance 6; say "simulation-distance: $sd -> 6"; fi
    else
        say "дистанции не тронуты (DISTANCE_TUNING=1 — включить)"
    fi
else
    warn "server.properties не найден"
fi

# --- 4. lagdoctor -----------------------------------------------------------
if [ -f "$SCRIPT_DIR/lagdoctor.sh" ] && [ "$SCRIPT_DIR" != "$(pwd)" ]; then
    cp -a "$SCRIPT_DIR/lagdoctor.sh" lagdoctor.sh
fi
[ -f lagdoctor.sh ] || warn "lagdoctor.sh не найден рядом с install.sh"
chmod +x lagdoctor.sh 2>/dev/null || true
say "lagdoctor.sh на месте"

cat <<'EOF'

Готово. Дальше:

  1) перезапусти сервер (не /reload);
  2) в логе проверь: "Server version 1.21.10 is set via property blib.server.version"
     и отсутствие ExceptionInInitializerError у BLib;
  3) запусти диагностику виновника 35% времени:

        bash lagdoctor.sh

     и пришли lag-report.txt.

Откат: файлы *.bak-lagfix-<дата> рядом с изменёнными.
EOF
