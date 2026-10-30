#!/usr/bin/env bash
# ============================================================================
#  Elytrix — откат установки Leaf к состоянию из бэкапа
# ----------------------------------------------------------------------------
#  Запуск:  bash rollback.sh [/root/RW_GRIEF] [/root/elytrix-backup-XXXX]
#  Без второго аргумента берёт самый свежий /root/elytrix-backup-*.
#
#  Возвращает все файлы, которые установщик заменил (REPLACED), удаляет те,
#  которых раньше не было (ADDED), и возвращает убранные остатки DivineMC
#  (REMOVED). Миры и данные игроков установщик не трогал — и откат тоже.
# ============================================================================
set -euo pipefail

DIR="${1:-/root/RW_GRIEF}"
BACKUP_ROOT="${BACKUP_ROOT:-/root}"
BK="${2:-}"

if [ -z "$BK" ]; then
    BK="$(ls -dt "$BACKUP_ROOT"/elytrix-backup-* 2>/dev/null | head -1 || true)"
fi
[ -n "${BK:-}" ] || { echo "Не найден бэкап $BACKUP_ROOT/elytrix-backup-*" >&2; exit 1; }
[ -d "$BK" ] || { echo "Каталог бэкапа $BK не существует" >&2; exit 1; }
[ -f "$BK/MANIFEST" ] || { echo "В $BK нет MANIFEST — это не бэкап установщика" >&2; exit 1; }
[ -d "$DIR" ] || { echo "Каталог сервера $DIR не найден" >&2; exit 1; }

# Процессы java с -jar ... .jar — именно сервер, а не случайная строка в чужой
# командной строке (иначе pgrep -f ловит сам установщик и ssh-команду).
server_pids() {
    local p cmd first
    for p in /proc/[0-9]*; do
        [ -r "$p/cmdline" ] || continue
        cmd="$(tr '\0' ' ' < "$p/cmdline" 2>/dev/null)" || continue
        [ -n "$cmd" ] || continue
        first="${cmd%% *}"
        case "${first##*/}" in java|javaw) ;; *) continue ;; esac
        case " $cmd " in *" -jar "*) ;; *) continue ;; esac
        printf '%s %s\n' "${p#/proc/}" "$cmd"
    done
}

RUNNING="$(server_pids)"
if [ -n "$RUNNING" ]; then
    echo "Сервер ещё запущен — сначала выполни stop." >&2
    printf '%s\n' "$RUNNING" >&2
    exit 1
fi

restored=0; removed=0; putback=0

while read -r action rel; do
    case "$action" in
        REPLACED)
            if [ -e "$BK/$rel" ]; then
                mkdir -p "$DIR/$(dirname "$rel")"
                cp -a "$BK/$rel" "$DIR/$rel"
                echo "  вернул   $rel"
                restored=$((restored + 1))
            fi
            ;;
        ADDED)
            if [ -e "$DIR/$rel" ]; then
                rm -f "$DIR/$rel"
                echo "  удалил   $rel"
                removed=$((removed + 1))
            fi
            ;;
        REMOVED)
            if [ -e "$BK/removed/$rel" ]; then
                mkdir -p "$DIR/$(dirname "$rel")"
                mv -f "$BK/removed/$rel" "$DIR/$rel"
                echo "  вернул   $rel"
                putback=$((putback + 1))
            fi
            ;;
    esac
done < "$BK/MANIFEST"

printf '\nОткат завершён: восстановлено %s, удалено %s, возвращено %s.\n' \
    "$restored" "$removed" "$putback"
cat <<NEXT

  Запусти сервер так, как запускал раньше:

    cd $DIR && bash start.sh

NEXT
