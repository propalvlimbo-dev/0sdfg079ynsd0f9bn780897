#!/usr/bin/env bash
# Полный снимок сервера в один архив: ядро, конфиги, start.sh, плагины их конфиги.
# Миры НЕ входят (они тяжёлые) — включаются флагом WITH_WORLDS=1.
#
#   bash backup-server.sh /root/RW_GRIEF
#   WITH_WORLDS=1 bash backup-server.sh /root/RW_GRIEF
set -euo pipefail
DIR=${1:-}
[ -n "$DIR" ] || { echo "использование: bash $0 <папка_сервера>" >&2; exit 1; }
[ -d "$DIR" ] || { echo "нет каталога $DIR" >&2; exit 1; }
DIR=$(readlink -f "$DIR")
NAME=$(basename "$DIR")
OUT="/root/${NAME}-backup-$(date +%Y%m%d-%H%M).tar.gz"

LIST=(
    "server.jar" "start.sh" "bukkit.yml" "spigot.yml" "pufferfish.yml" "purpur.yml"
    "server.properties" "commands.yml" "permissions.yml" "help.yml" "whitelist.json" "ops.json"
    "config" "plugins" "logs/latest.log"
)
EXTRA=()
[ "${WITH_WORLDS:-0}" = "1" ] && EXTRA=(world world_nether world_the_end world_spawn world_siege boss duels)

cd "$DIR"
EXIST=()
for p in "${LIST[@]}" "${EXTRA[@]}"; do [ -e "$p" ] && EXIST+=("$p"); done
echo "архив: $OUT"
echo "внутри: ${EXIST[*]}"
tar czf "$OUT" --warning=no-file-changed "${EXIST[@]}" 2>/dev/null || true
ls -lh "$OUT"
echo ""
echo "готово. Скачать к себе:"
echo "  scp root@<адрес-сервера>:$OUT ."
