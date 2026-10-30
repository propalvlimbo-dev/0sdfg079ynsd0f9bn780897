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
