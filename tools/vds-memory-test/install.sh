#!/usr/bin/env bash
# Experimental, narrow change: leave Xmx and the rest of the live script intact.
set -euo pipefail
file="${1:-/root/RW_GRIEF/start.sh}"
if [[ ! -f "$file" || -L "$file" ]]; then
  echo "ОШИБКА: не найден обычный файл запуска (символические ссылки не поддерживаются): $file" >&2
  exit 1
fi
# Require exactly one occurrence of each heap flag and an exact standalone line.
for flag in Xms Xmx; do
  count=$( (grep -oE -- "-${flag}[^[:space:]\\\\]*" "$file" || true) | wc -l)
  if [[ "$count" -ne 1 ]]; then
    echo "ОШИБКА: ожидался ровно один параметр -$flag; файл не изменён." >&2
    exit 1
  fi
done
if ! grep -qE '^[[:space:]]*-Xms10G[[:space:]]*\\[[:space:]]*$' "$file" || \
   ! grep -qE '^[[:space:]]*-Xmx10G[[:space:]]*\\[[:space:]]*$' "$file"; then
  echo 'ОШИБКА: ожидались отдельные строки -Xms10G и -Xmx10G; файл не изменён.' >&2
  exit 1
fi
backup=$(mktemp "${file}.before-xms8.XXXXXXXX")
tmp=$(mktemp "${file}.xms-test.XXXXXXXX")
trap 'rm -f -- "$tmp"' EXIT
cp -p -- "$file" "$backup"
cp -p -- "$file" "$tmp"
sed 's/^\([[:space:]]*\)-Xms10G\([[:space:]]*\\[[:space:]]*\)$/\1-Xms8G\2/' "$file" > "$tmp"
bash -n "$tmp"
if ! grep -qE '^[[:space:]]*-Xms8G[[:space:]]*\\[[:space:]]*$' "$tmp"; then
  echo 'ОШИБКА: изменение не прошло проверку; исходный файл не изменён.' >&2
  exit 1
fi
mv -f -- "$tmp" "$file"
echo "Изменено: $file — Xms8G, Xmx10G; остальные параметры сохранены."
echo "Резервная копия: $backup"
echo 'Действующую JVM это не меняет: нужен полный новый запуск через этот скрипт.'
