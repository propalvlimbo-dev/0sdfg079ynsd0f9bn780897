#!/usr/bin/env bash
# Rebuild from an UNPATCHED 3.2.3 jar. Needs Java, ECJ and the repository's BLib.jar (ASM).
set -euo pipefail
if [ "$#" -ne 2 ] || [ -z "${JAVA:-}" ] || [ -z "${ECJ:-}" ]; then
  echo 'Usage: JAVA=/path/to/java ECJ=/path/to/ecj.jar build.sh input.jar output.jar' >&2; exit 2
fi
root=$(cd "$(dirname "$0")/../.." && pwd)
input=$(realpath "$1"); output=$(realpath -m "$2")
[ "$input" != "$output" ] || { echo "Input and output must differ" >&2; exit 2; }
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/classes" "$tmp/patch" "$tmp/jar"
"$JAVA" -jar "$ECJ" -21 -proc:none -d "$tmp/classes" $(find "$root/tools/freakmodel-fix/stubs" -name '*.java') "$root/tools/freakmodel-fix/src/pw/elytrix/freakmodel/PlayerBodyTracker.java" "$root/tools/freakmodel-fix/test/TrackerTest.java"
"$JAVA" -Xverify:all -cp "$tmp/classes" TrackerTest
"$JAVA" -jar "$ECJ" -21 -proc:none -cp "$root/plugins/BLib.jar" -d "$tmp/patch" "$root/tools/freakmodel-fix/src/PatchRig.java" "$root/tools/freakmodel-fix/test/LinkTest.java"
(cd "$tmp/jar" && unzip -q "$input")
cp "$tmp/classes"/pw/elytrix/freakmodel/PlayerBodyTracker*.class "$tmp/jar/pw/elytrix/freakmodel/"
"$JAVA" -cp "$tmp/patch:$root/plugins/BLib.jar" PatchRig "$tmp/jar/pw/elytrix/freakmodel/WornAngelRig.class"
"$JAVA" -cp "$tmp/patch:$root/plugins/BLib.jar" LinkTest "$tmp/jar"
sed -i 's/^version: 3\.2\.3$/version: 3.2.10/' "$tmp/jar/plugin.yml"
rm -f "$output"
(cd "$tmp/jar" && zip -qr "$output" .)
