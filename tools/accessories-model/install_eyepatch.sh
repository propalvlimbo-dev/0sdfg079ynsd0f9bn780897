#!/usr/bin/env bash
# ============================================================================
#  Elytrix — маска и сороконожка, сборка без падения /аксессуары (v26)
# ----------------------------------------------------------------------------
#  Что делает:
#    * кладёт ElytrixFreakModel 3.6.1 (меню без кнопки «Назад», «Снять всё»
#      внизу по центру, маска = 3D-модель на голове, сороконожка = живой питомец
#      над головой, любая ошибка аксессуара больше не ломает команду);
#    * обновляет ресурспак и ElytrixRP/config.yml (новый SHA-1);
#    * печатает контрольные суммы, чтобы можно было проверить руками.
#
#  Запуск:  bash install.sh [/root/RW_GRIEF]        (sh install.sh тоже работает)
# ============================================================================
if [ -z "${BASH_VERSION:-}" ]; then
    exec /bin/bash "$0" "$@"
fi
set -euo pipefail

DIR="${1:-/root/RW_GRIEF}"
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
RP_NAME="Elytrix-RP-1.21.zip"

say()  { printf '\033[1m==> %s\033[0m\n' "$*"; }
ok()   { printf '    \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '    \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

say "1/5  Проверки"
[ -d "$DIR" ] || die "нет каталога сервера: $DIR"
[ -f "$SELF_DIR/plugins/ElytrixFreakModel.jar" ] || die "в архиве нет plugins/ElytrixFreakModel.jar"
[ -f "$SELF_DIR/rp/$RP_NAME" ] || die "в архиве нет rp/$RP_NAME"
ok "каталог сервера: $DIR"
if pgrep -af 'java.*-jar (server|leaf|paper)\.jar' >/dev/null 2>&1; then
    warn "сервер, похоже, запущен — файлы заменятся, но изменения подхватит только restart"
fi

say "2/5  Плагин аксессуаров"
install -m 644 "$SELF_DIR/plugins/ElytrixFreakModel.jar" "$DIR/plugins/ElytrixFreakModel.jar"
ok "plugins/ElytrixFreakModel.jar  $(sha256sum "$DIR/plugins/ElytrixFreakModel.jar" | cut -d' ' -f1)"

say "3/5  Ресурспак"
mkdir -p "/root/RP" 2>/dev/null || true
if [ -w /root/RP ] || [ "$(id -u)" = "0" ]; then
    install -m 644 "$SELF_DIR/rp/$RP_NAME" "/root/RP/$RP_NAME"
    ok "/root/RP/$RP_NAME"
fi
mkdir -p "$DIR/rp"
install -m 644 "$SELF_DIR/rp/$RP_NAME" "$DIR/rp/$RP_NAME"
ok "$DIR/rp/$RP_NAME"
NEW_SHA1="$(sha1sum "$DIR/rp/$RP_NAME" | cut -d' ' -f1)"

say "4/5  ElytrixRP/config.yml"
CONFIG="$DIR/plugins/ElytrixRP/config.yml"
mkdir -p "$DIR/plugins/ElytrixRP"
if [ -f "$CONFIG" ]; then
    sed -i -E "s|^([[:space:]]*sha1[[:space:]]*:).*|\1 \"$NEW_SHA1\"|" "$CONFIG"
    ok "sha1 в конфиге обновлён (остальные настройки не тронуты)"
else
    install -m 644 "$SELF_DIR/plugins/ElytrixRP/config.yml" "$CONFIG"
    ok "конфиг установлен"
fi

say "5/5  Модели ModelEngine"
if [ -d "$SELF_DIR/plugins/ModelEngine" ]; then
    cp -a "$SELF_DIR/plugins/ModelEngine/." "$DIR/plugins/ModelEngine/"
    ok "blueprints и assets обновлены"
fi

printf '\n'
printf '  Ресурспак:  %s\n' "$NEW_SHA1"
printf '  Плагин:     %s\n' "$(sha256sum "$DIR/plugins/ElytrixFreakModel.jar" | cut -d' ' -f1)"
printf '  Версия:     %s\n' "$(unzip -p "$DIR/plugins/ElytrixFreakModel.jar" plugin.yml | grep -m1 '^version' | cut -d' ' -f2)"
printf '\n'
printf '  Дальше:  restart  (или stop → bash start.sh)\n'
printf '  Проверка в логе:  grep -iE "ElytrixFreakModel|ModelEngine" logs/latest.log | tail -20\n'
