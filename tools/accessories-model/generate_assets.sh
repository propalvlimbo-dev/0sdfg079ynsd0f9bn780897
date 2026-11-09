#!/bin/sh
# Generate ModelEngine resource-pack assets for one blueprint, byte-identical to the live generator.
#
#   JAVA=/path/to/java ECJ=/path/to/ecj.jar sh tools/accessories-model/generate_assets.sh \
#       tools/accessories-model/elytrix_kaneki_tentacles.bbmodel /tmp/kaneki-assets
#
# The real ModelEngine 4.1.0 parser runs against stand-ins for Bukkit/fastutil/slf4j from ./stubs.
# plugins/ is never written: only the requested output directory is created.
set -eu
[ -n "${JAVA:-}" ] && [ -n "${ECJ:-}" ] || { echo 'Set JAVA and ECJ' >&2; exit 2; }
[ $# -eq 2 ] || { echo "Usage: $0 <blueprint.bbmodel> <new-output-dir>" >&2; exit 2; }
here=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
root=$(CDPATH= cd -- "$here/../.." && pwd)
blueprint=$1
out=$2
[ -f "$blueprint" ] || { echo "Missing blueprint: $blueprint" >&2; exit 2; }
case "$out" in
  "$root"/plugins/*|"$root"/rp/*) echo 'Refusing to write into plugins/ or rp/' >&2; exit 2 ;;
esac
[ -e "$out" ] && { echo "Output already exists: $out" >&2; exit 2; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
# TMath touches Bukkit statics when it initializes, so the copy used by the parser is patched.
unzip -p "$root/plugins/ModelEngine-4.1.0.jar" com/ticxo/modelengine/api/utils/math/TMath.class > "$tmp/TMath.class"
find "$here/stubs" -name '*.java' > "$tmp/stubs.txt"
"$JAVA" -jar "$ECJ" -21 -proc:none -nowarn \
    -cp "$root/plugins/BLib.jar:$root/plugins/ModelEngine-4.1.0.jar" \
    -d "$tmp" "$here/PatchTMath.java" "$here/GenerateAssets.java" @"$tmp/stubs.txt"
"$JAVA" -cp "$tmp:$root/plugins/BLib.jar" PatchTMath \
    "$tmp/TMath.class" "$tmp/com/ticxo/modelengine/api/utils/math/TMath.class"
"$JAVA" -Xverify:all -Dmodelengine.test.rotation=false \
    -cp "$tmp:$root/plugins/ModelEngine-4.1.0.jar:$root/plugins/BLib.jar:$root/plugins/FancyNpcs-2.10.0.jar" \
    GenerateAssets "$blueprint" "$out"
