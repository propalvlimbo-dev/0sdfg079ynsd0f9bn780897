#!/bin/sh
# Isolated mock test ONLY. Never patches the original JAR or writes plugins/.
set -eu
[ -n "${JAVA:-}" ] && [ -n "${ECJ:-}" ] || { echo 'Set JAVA and ECJ' >&2; exit 2; }
root=$(CDPATH= cd -- "$(dirname "$0")/../../.." && pwd)
dir="$root/tools/accessories-draft/modelengine-test"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
unzip -p "$root/plugins/ModelEngine-4.1.0.jar" com/ticxo/modelengine/api/utils/math/TMath.class > "$tmp/TMath.class"
# All stub classes shadow platform APIs in this temporary test JVM only.
find "$dir/stubs" -name '*.java' > "$tmp/stubs.txt"
"$JAVA" -jar "$ECJ" -21 -proc:none -cp "$root/plugins/BLib.jar:$root/plugins/ModelEngine-4.1.0.jar" -d "$tmp" "$dir/PatchTMath.java" "$dir/ParseModel.java" "$dir/ParseBlueprint.java" @"$tmp/stubs.txt"
"$JAVA" -cp "$tmp:$root/plugins/BLib.jar" PatchTMath "$tmp/TMath.class" "$tmp/com/ticxo/modelengine/api/utils/math/TMath.class"
classpath="$tmp:$root/plugins/ModelEngine-4.1.0.jar:$root/plugins/BLib.jar:$root/plugins/FancyNpcs-2.10.0.jar"
model="$root/tools/accessories-draft/elytrix_kaneki_tentacles.bbmodel"
"$JAVA" -Xverify:all -cp "$classpath" ParseModel "$model"
"$JAVA" -Xverify:all -cp "$classpath" ParseBlueprint "$model"
