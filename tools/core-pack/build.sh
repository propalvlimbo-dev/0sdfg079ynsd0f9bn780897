#!/usr/bin/env bash
# Собирает elytrix-server-pack-v1.zip из текущего содержимого репозитория.
#   cd <repo> && bash tools/core-pack/build.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
REPO=$(pwd)
NAME=elytrix-server-pack-v1
STAGE=$(mktemp -d)
PK="$STAGE/$NAME"
mkdir -p "$PK/configs/config" "$PK/tools"

cp tools/core-pack/README.md        "$PK/README.md"
cp tools/core-pack/assets/apply.sh  "$PK/apply.sh"
cp tools/core-pack/assets/download-core.sh "$PK/download-core.sh"
cp tools/core-pack/assets/backup-server.sh "$PK/backup-server.sh"
cp tools/core-pack/assets/server.properties "$PK/server.properties"
cp start.sh.tuned "$PK/start.sh" 2>/dev/null || cp tools/core-install/start.sh "$PK/start.sh"

for f in bukkit.yml spigot.yml pufferfish.yml purpur.yml; do
    cp "$REPO/$f" "$PK/configs/$f"
done
for f in paper-global.yml paper-world-defaults.yml leaf-global.yml gale-global.yml gale-world-defaults.yml; do
    cp "$REPO/config/$f" "$PK/configs/config/$f"
done

mkdir -p "$PK/tools/lagfix"
for f in install.sh lagdoctor.sh spark30.sh jfr30.sh fixall.sh tune.sh README.md; do
    [ -f "tools/lagfix/$f" ] && cp "tools/lagfix/$f" "$PK/tools/lagfix/$f"
done

chmod +x "$PK"/*.sh "$PK"/tools/lagfix/*.sh
# chmod в zip не сохраняется — распаковка даёт 644, поэтому README говорит про bash <файл>

( cd "$STAGE" && zip -qr "$REPO/$NAME.zip" "$NAME" )
rm -rf "$STAGE"
unzip -l "$REPO/$NAME.zip" | tail -5
sha256sum "$REPO/$NAME.zip"
