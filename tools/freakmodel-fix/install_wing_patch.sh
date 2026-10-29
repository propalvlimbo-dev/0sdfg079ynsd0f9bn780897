#!/usr/bin/env bash
# Install the 3.2.9 delta without overwriting live configs/caches or touching :8085.
set -euo pipefail
umask 077
if [[ $# != 1 || ! -f "$1" ]]; then
  echo 'Usage: install_wing_patch.sh /path/to/elytrix-freakmodel-patch.zip' >&2
  exit 2
fi
archive=$(realpath "$1")
server=${ELYTRIX_SERVER_ROOT:-/root/RW_GRIEF}
rpdir=${ELYTRIX_RP_DIR:-/root/RP}
backup_root=${ELYTRIX_BACKUP_ROOT:-/root/elytrix-backups}
config="$server/plugins/ElytrixRP/config.yml"
plugin=plugins/ElytrixFreakModel.jar
blueprint=plugins/ModelEngine/blueprints/elytrix_angel_wings.bbmodel
modeldir='plugins/ModelEngine/resource pack/assets/modelengine/models/elytrix_angel_wings'
rp=rp/Elytrix-RP-1.21.zip
sha1=d6701c4da33bd86b3fa25732f2bad882cdbecf7d
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
unzip -tq "$archive"
unzip -oq "$archive" -d "$work"
printf '%s  %s\n' '41fa5d97830fdbf6af1f3ca5f62ed5d96ca7580e6e95b5e8cc34a69d7d757d80' "$work/$plugin" | sha256sum -c
printf '%s  %s\n' 'ce030b8e09b4cca445b34ad4097d82f788d073cb768bf5aaa77ff41eaf8d660e' "$work/$blueprint" | sha256sum -c
printf '%s  %s\n' 'a8391b404dcaa0355f570c2a2702e8d6c486ab0f7e1ef2f06a99170788f58b66' "$work/$modeldir/left_wing_inner.json" | sha256sum -c
printf '%s  %s\n' 'bfe7d5e870b22d202dd984c038589c222dc044a3f636284eacaa08ffd948181b' "$work/$modeldir/right_wing_inner.json" | sha256sum -c
printf '%s  %s\n' "$sha1" "$work/$rp" | sha1sum -c
for f in "$server/$plugin" "$server/$blueprint" "$server/$rp" "$rpdir/Elytrix-RP-1.21.zip" "$config"; do
  if [[ ! -f "$f" ]]; then echo "Required live file not found: $f" >&2; exit 1; fi
done
# Preserve a deliberately symlinked live configuration instead of replacing the link.
config=$(realpath "$config")
if [[ $(grep -cE '^[[:space:]]*sha1[[:space:]]*:' "$config" || true) != 1 ]]; then
  echo 'Expected exactly one sha1 entry in the live ElytrixRP config; no changes applied.' >&2
  exit 1
fi
mkdir -p "$backup_root"
backup=$(mktemp -d "$backup_root/efm-3.2.9-XXXXXXXX")
cp -p "$server/$plugin" "$backup/ElytrixFreakModel.jar"
cp -p "$server/$blueprint" "$backup/elytrix_angel_wings.bbmodel"
cp -p "$server/$rp" "$backup/server-resource-pack.zip"
cp -p "$rpdir/Elytrix-RP-1.21.zip" "$backup/served-resource-pack.zip"
cp -p "$config" "$backup/ElytrixRP-config.yml"
for side in left right; do
  file="$server/$modeldir/${side}_wing_inner.json"
  if [[ -f "$file" ]]; then cp -p "$file" "$backup/${side}_wing_inner.json"; fi
done
echo "Backup created: $backup"
# Stage each replacement on the destination filesystem and rename atomically.
atomic_install() {
  local source=$1 destination=$2 dir temp
  if [[ -L "$destination" ]]; then destination=$(realpath "$destination"); fi
  dir=$(dirname "$destination")
  mkdir -p "$dir"
  temp=$(mktemp "$dir/.efm-3.2.9-XXXXXXXX")
  if ! install -m 644 "$source" "$temp"; then rm -f "$temp"; return 1; fi
  if ! mv -f "$temp" "$destination"; then rm -f "$temp"; return 1; fi
}
atomic_install "$work/$blueprint" "$server/$blueprint"
for side in left right; do
  atomic_install "$work/$modeldir/${side}_wing_inner.json" "$server/$modeldir/${side}_wing_inner.json"
done
atomic_install "$work/$rp" "$server/$rp"
atomic_install "$work/$rp" "$rpdir/Elytrix-RP-1.21.zip"
sed -i -E "s/^([[:space:]]*)sha1[[:space:]]*:.*/\\1sha1: \"$sha1\"/" "$config"
atomic_install "$work/$plugin" "$server/$plugin"
sha1sum "$rpdir/Elytrix-RP-1.21.zip"
echo 'Installation complete. Restart the Minecraft server; do not use /reload.'
