#!/usr/bin/env bash
# ============================================================================
#  Elytrix — установка Leaf 1.21.11 + оптимизированные конфиги + фикс плагина
# ----------------------------------------------------------------------------
#  Запуск:   bash install.sh [/root/RW_GRIEF]
#
#  Что делает (и чего НЕ делает):
#   1. проверяет Java 21+, свободное место и что сервер не запущен;
#   2. складывает всё текущее в /root/elytrix-backup-<дата>/ + MANIFEST;
#   3. скачивает Leaf 1.21.11-179 с GitHub и сверяет SHA-256;
#   4. ставит оптимизированные конфиги ядра;
#   5. ставит новый start.sh (heap, GC-лог, без 100 мс, автоперезапуск);
#   6. ставит ElytrixFreakModel v21 (меню не может выключить весь плагин);
#   7. уводит в бэкап остатки DivineMC (versions/, divinemc*.yml, purpur.yml);
#   8. печатает, что дальше делать и как откатиться.
#
#  НЕ трогает: миры, players/, plugins/*/данные, server.properties, eula.txt,
#  ресурспак, остальные плагины.
# ============================================================================
# Скрипт написан под bash (массивы, pipefail). Если его запустили через sh/dash,
# перезапускаем себя правильным интерпретатором — иначе будет "Syntax error".
if [ -z "${BASH_VERSION:-}" ]; then
    exec /bin/bash "$0" "$@"
fi

set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIR="${1:-/root/RW_GRIEF}"
BACKUP_ROOT="${BACKUP_ROOT:-/root}"

LEAF_VERSION="1.21.11-179"
LEAF_URL="https://github.com/Winds-Studio/Leaf/releases/download/ver-1.21.11/leaf-1.21.11-179.jar"
LEAF_SHA="5da79782215c1a25edcd7c73b3523b7ecb7f4b86dc8a5846a176ed69bc2cd020"
LEAF_SIZE="83953995"
PLUGIN_SHA="44ad787637117a26c7e45cb6708b6892920c3d2ccc1d6496439ebc363111bf55"

Y=$'\033[33m'; G=$'\033[32m'; R=$'\033[31m'; B=$'\033[1m'; N=$'\033[0m'
step() { printf '\n%s==> %s%s\n' "$B" "$*" "$N"; }
info() { printf '    %s\n' "$*"; }
ok()   { printf '    %s✓%s %s\n' "$G" "$N" "$*"; }
warn() { printf '    %s!%s %s\n' "$Y" "$N" "$*"; }
die()  { printf '\n%sОШИБКА:%s %s\n' "$R" "$N" "$*" >&2; exit 1; }

# Процессы java, запущенные именно с ядром ИЗ ЭТОГО каталога (server.jar/leaf.jar/...).
# Важно: прокси вроде NullCordX.jar рядом на машине нас не интересует, как и чужие
# строки в командной строке — поэтому смотрим /proc/<pid>/cmdline, находим -jar
# и сверяем путь к jar с каталогом установки.
server_pids() {
    local p args jar cwd target dir_real name
    for p in /proc/[0-9]*; do
        [ -r "$p/cmdline" ] || continue
        mapfile -d '' -t args < "$p/cmdline" 2>/dev/null || continue
        [ "${#args[@]}" -gt 0 ] || continue
        case "${args[0]##*/}" in java|javaw) ;; *) continue ;; esac
        jar=""
        local i
        for ((i = 0; i < ${#args[@]}; i++)); do
            if [ "${args[i]}" = "-jar" ]; then jar="${args[i+1]:-}"; break; fi
        done
        [ -n "$jar" ] || continue
        cwd="$(readlink -f "$p/cwd" 2>/dev/null || echo /)"
        case "$jar" in
            /*) target="$(readlink -f "$jar" 2>/dev/null || echo "$jar")" ;;
            *)  target="$(readlink -f "$cwd/$jar" 2>/dev/null || echo "$cwd/$jar")" ;;
        esac
        name="${target##*/}"
        case "$name" in server.jar|leaf.jar|paper.jar|purpur.jar|spigot.jar|craftbukkit.jar) ;; *) continue ;; esac
        dir_real="$(readlink -f "$DIR")"
        [ "$(dirname "$target")" = "$dir_real" ] || continue
        printf '%s %s\n' "${p#/proc/}" "$target"
    done
}


# ---------------------------------------------------------------- 1. проверки
step "1/8  Проверки"

[ -d "$DIR" ]            || die "каталог $DIR не найден"
[ -d "$DIR/plugins" ]    || die "в $DIR нет каталога plugins — это точно каталог сервера?"
[ -f "$DIR/eula.txt" ]   || warn "eula.txt не найден: сервер не запустится, пока не будет eula=true"
[ -w "$DIR" ]            || die "нет прав на запись в $DIR (запусти от root)"

RUNNING="$(server_pids)"
if [ -n "$RUNNING" ]; then
    printf '\n%sСервер ещё запущен:%s\n' "$R" "$N"
    printf '%s\n' "$RUNNING" | sed 's/^/    /'
    die "сначала останови сервер командой stop (или: screen -S mc -X stuff \"stop\\n\"), потом запусти установку снова"
fi
ok "сервер не запущен"

JAVA_BIN="${JAVA_BIN:-}"
if [ -z "$JAVA_BIN" ]; then
    for cand in java /usr/lib/jvm/*/bin/java /opt/java/*/bin/java /usr/java/*/bin/java /opt/*/bin/java; do
        [ -x "$cand" ] && { JAVA_BIN="$cand"; break; }
    done
fi
[ -n "$JAVA_BIN" ] || die "Java не найдена. Поставь Java 21 и повтори"
JAVA_MAJOR="$("$JAVA_BIN" -version 2>&1 | awk -F'"' '/ version /{print $2; exit}' \
    | awk -F. '{ if ($1 == "1") print $2; else print $1 }')"
case "$JAVA_MAJOR" in ''|*[!0-9]*) die "не удалось определить версию Java ($JAVA_BIN)" ;; esac
[ "$JAVA_MAJOR" -ge 21 ] || die "Leaf 1.21.11 требует Java 21+, у тебя Java $JAVA_MAJOR ($JAVA_BIN)"
ok "Java $JAVA_MAJOR: $JAVA_BIN"

FREE_MB="$(df -Pk "$DIR" | awk 'NR==2 {print int($4 / 1024)}')"
[ "${FREE_MB:-0}" -ge 600 ] || die "мало места на диске: ${FREE_MB} МБ свободно, нужно минимум 600"
ok "свободно ${FREE_MB} МБ"

for tool in sha256sum unzip; do
    command -v "$tool" >/dev/null 2>&1 || die "не найден $tool"
done
if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
    die "не найдены curl/wget — нечем скачать ядро"
fi

# ------------------------------------------------------------------- 2. бэкап
step "2/8  Бэкап текущего состояния"

BK="$BACKUP_ROOT/elytrix-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BK"
: > "$BK/MANIFEST"

BACKUP_FILES=(
    "server.jar"
    "start.sh"
    "bukkit.yml"
    "spigot.yml"
    "pufferfish.yml"
    "purpur.yml"
    "config/paper-global.yml"
    "config/paper-world-defaults.yml"
    "config/leaf-global.yml"
    "config/gale-global.yml"
    "config/gale-world-defaults.yml"
    "plugins/ElytrixFreakModel.jar"
    "plugins/LagFixer/modules/WorldCleaner.yml"
)
for rel in "${BACKUP_FILES[@]}"; do
    if [ -e "$DIR/$rel" ]; then
        mkdir -p "$BK/$(dirname "$rel")"
        cp -a "$DIR/$rel" "$BK/$rel"
        echo "REPLACED $rel" >> "$BK/MANIFEST"
    fi
done
info "бэкап: $BK"
info "файлов сохранено: $(grep -c REPLACED "$BK/MANIFEST" || true)"

# -------------------------------------------------------------------- 3. ядро
step "3/8  Ядро Leaf $LEAF_VERSION"

LEAF_JAR="${LEAF_JAR:-}"
if [ -n "$LEAF_JAR" ]; then
    [ -f "$LEAF_JAR" ] || die "LEAF_JAR=$LEAF_JAR не найден"
    info "беру готовый файл $LEAF_JAR (скачивание пропущено)"
else
    TMP_JAR="/tmp/leaf-${LEAF_VERSION}.jar"
    if [ -f "$TMP_JAR" ] && [ "$(stat -c %s "$TMP_JAR")" = "$LEAF_SIZE" ]; then
        info "использую уже скачанный $TMP_JAR"
    else
        info "скачиваю $LEAF_URL"
        info "это ~80 МБ, может занять пару минут..."
        if command -v curl >/dev/null 2>&1; then
            curl -fL --retry 3 --retry-delay 3 --connect-timeout 20 \
                 --progress-bar -o "$TMP_JAR.part" "$LEAF_URL" \
                || die "не удалось скачать ядро. Проверь интернет и повтори (файл можно положить рядом: LEAF_JAR=/путь/leaf.jar bash install.sh)"
        else
            wget -q --show-progress -O "$TMP_JAR.part" "$LEAF_URL" \
                || die "не удалось скачать ядро через wget"
        fi
        mv -f "$TMP_JAR.part" "$TMP_JAR"
    fi
    LEAF_JAR="$TMP_JAR"
fi

ACTUAL_SHA="$(sha256sum "$LEAF_JAR" | awk '{print $1}')"
if [ "$ACTUAL_SHA" != "$LEAF_SHA" ]; then
    printf '\n    ожидался SHA-256: %s\n    получен         : %s\n' "$LEAF_SHA" "$ACTUAL_SHA"
    die "контрольная сумма ядра не совпала — файл битый или подменён, установку остановил"
fi
unzip -l "$LEAF_JAR" >/dev/null 2>&1 || die "скачанный файл не является jar-архивом"
ok "SHA-256 совпал: $LEAF_SHA"

install -m 644 "$LEAF_JAR" "$DIR/server.jar"
[ "$(sha256sum "$DIR/server.jar" | awk '{print $1}')" = "$LEAF_SHA" ] || die "server.jar записался неверно"
ok "server.jar установлен ($(du -h "$DIR/server.jar" | cut -f1))"

# ----------------------------------------------------------------- 4. конфиги
step "4/8  Оптимизированные конфиги"

install_file() {
    local rel="$1" src="$2" dest="$DIR/$1"
    [ -f "$src" ] || die "в пакете нет файла $rel"
    mkdir -p "$(dirname "$dest")"
    if [ -e "$BK/$rel" ]; then
        :
    else
        echo "ADDED $rel" >> "$BK/MANIFEST"
    fi
    install -m 644 "$src" "$dest"
    cmp -s "$src" "$dest" || die "файл $rel записался неверно"
    ok "$rel"
}

install_file "bukkit.yml"                         "$SELF_DIR/files/bukkit.yml"
install_file "spigot.yml"                         "$SELF_DIR/files/spigot.yml"
install_file "pufferfish.yml"                     "$SELF_DIR/files/pufferfish.yml"
install_file "config/paper-global.yml"            "$SELF_DIR/files/config/paper-global.yml"
install_file "config/paper-world-defaults.yml"    "$SELF_DIR/files/config/paper-world-defaults.yml"
install_file "config/leaf-global.yml"             "$SELF_DIR/files/config/leaf-global.yml"
install_file "config/gale-global.yml"             "$SELF_DIR/files/config/gale-global.yml"
install_file "config/gale-world-defaults.yml"     "$SELF_DIR/files/config/gale-world-defaults.yml"

if [ -d "$DIR/plugins/LagFixer/modules" ]; then
    install_file "plugins/LagFixer/modules/WorldCleaner.yml" \
                 "$SELF_DIR/files/plugins/LagFixer/modules/WorldCleaner.yml"
else
    warn "LagFixer не найден — пропускаю его конфиг"
fi

# ---------------------------------------------------------------- 5. start.sh
step "5/8  start.sh"

[ -f "$SELF_DIR/start.sh" ] || die "в пакете нет start.sh"
install -m 755 "$SELF_DIR/start.sh" "$DIR/start.sh"
bash -n "$DIR/start.sh" || die "новый start.sh не проходит проверку синтаксиса"
ok "start.sh (heap 60% RAM, GC-лог, цель паузы 200 мс, автоперезапуск)"

# ------------------------------------------------------------- 6. фикс плагина
step "6/8  Аксессуары: плагин и ресурспак"

NEW_PLUGIN="$SELF_DIR/plugins/ElytrixFreakModel.jar"
[ -f "$NEW_PLUGIN" ] || die "в пакете нет ElytrixFreakModel.jar"
[ "$(sha256sum "$NEW_PLUGIN" | awk '{print $1}')" = "$PLUGIN_SHA" ] \
    || die "jar плагина в пакете повреждён (SHA-256 не совпал)"
install -m 644 "$NEW_PLUGIN" "$DIR/plugins/ElytrixFreakModel.jar"
ok "плагин обновлён (SHA-256 $PLUGIN_SHA)"

# Модели аксессуаров (маска, сороконожка, крылья, кагуне) — без них ModelEngine
# поднимет плагин, но меню не найдёт blueprint'ы и честно скажет об этом в лог.
if [ -d "$SELF_DIR/plugins/ModelEngine" ]; then
    mkdir -p "$DIR/plugins/ModelEngine"
    cp -a "$SELF_DIR/plugins/ModelEngine/." "$DIR/plugins/ModelEngine/"
    MODELS=$(find "$DIR/plugins/ModelEngine/blueprints" -maxdepth 1 -name '*.bbmodel' 2>/dev/null | wc -l)
    ok "модели ModelEngine: $MODELS blueprint(ов) в plugins/ModelEngine/blueprints"
fi

# Повязка Канэки — это слой брони, его рисует клиент, поэтому она живёт в паке.
NEW_PACK="$SELF_DIR/rp/Elytrix-RP-1.21.zip"
if [ -f "$NEW_PACK" ]; then
    mkdir -p "$DIR/rp" "$DIR/plugins/ElytrixRP"
    install -m 644 "$NEW_PACK" "$DIR/rp/Elytrix-RP-1.21.zip"
    if mkdir -p /root/RP 2>/dev/null && [ -w /root/RP ]; then
        install -m 644 "$NEW_PACK" /root/RP/Elytrix-RP-1.21.zip
    fi
    PACK_SHA1="$(sha1sum "$DIR/rp/Elytrix-RP-1.21.zip" | cut -d' ' -f1)"
    install -m 644 "$SELF_DIR/plugins/ElytrixRP/config.yml" "$DIR/plugins/ElytrixRP/config.yml"
    sed -i -E "s|^([[:space:]]*sha1[[:space:]]*:).*|\1 \"$PACK_SHA1\"|" "$DIR/plugins/ElytrixRP/config.yml"
    ok "ресурспак $PACK_SHA1 (+ plugins/ElytrixRP/config.yml)"
fi

# --------------------------------------------------------- 7. остатки DivineMC
step "7/8  Остатки DivineMC"

moved=0
shopt -s nullglob
for f in "$DIR"/divinemc*.yml "$DIR"/DivineMC* "$DIR"/config/divinemc* ; do
    mkdir -p "$BK/removed"
    mv "$f" "$BK/removed/"
    echo "REMOVED $(basename "$f")" >> "$BK/MANIFEST"
    info "убран $(basename "$f")"
    moved=$((moved + 1))
done
if [ -e "$DIR/purpur.yml" ]; then
    mkdir -p "$BK/removed"
    mv "$DIR/purpur.yml" "$BK/removed/purpur.yml"
    echo "REMOVED purpur.yml" >> "$BK/MANIFEST"
    info "убран purpur.yml (Leaf не читает конфиг Purpur)"
    moved=$((moved + 1))
fi
if [ -d "$DIR/versions" ]; then
    mkdir -p "$BK/removed"
    mv "$DIR/versions" "$BK/removed/versions"
    echo "REMOVED versions/" >> "$BK/MANIFEST"
    info "убран кэш versions/ (иначе paperclip может подсунуть старое ядро)"
    moved=$((moved + 1))
fi
[ "$moved" -eq 0 ] && info "нечего убирать"

# ----------------------------------------------------------------- 8. итог
step "8/8  Готово"

cat > "$BK/info.txt" <<INFO
Elytrix: установка Leaf
дата:        $(date -Is)
каталог:     $DIR
ядро:        Leaf $LEAF_VERSION
jar SHA-256: $LEAF_SHA
плагин:      ElytrixFreakModel v21 ($PLUGIN_SHA)
java:        $JAVA_BIN (Java $JAVA_MAJOR)
heap:        по start.sh (60% RAM, 3..12 ГБ)
бэкап:       $BK
откат:       bash $BK/rollback.sh $DIR
INFO

# кладём рядом готовый откат, чтобы он работал даже если пакет удалят
cp -f "$SELF_DIR/rollback.sh" "$BK/rollback.sh" 2>/dev/null || true
chmod +x "$BK/rollback.sh" 2>/dev/null || true

printf '\n%sУстановлено.%s Ядро: Leaf %s. Бэкап: %s\n' "$G" "$N" "$LEAF_VERSION" "$BK"
cat <<NEXT

  Дальше:

    cd $DIR && bash start.sh

  (если сервер запускается через screen/tmux — тем же способом, что и раньше,
   например:  screen -dmS mc bash $DIR/start.sh )

  Что проверить в логе после старта:
    1) строка "Done (" и «Leaf version 1.21.11» — ядро поднялось;
    2) нет "Your configuration is outdated" — если есть, это нормально,
       Leaf сам допишет новые ключи, значения из пакета останутся;
    3) нет "ElytrixFreakModel ... plugin is disabled";
    4) /аксессуары открывается;
    5) spark:  spark health   — и через 10 минут  spark tps.

  Если что-то пошло не так — откат одной командой:

    bash $BK/rollback.sh $DIR

NEXT
