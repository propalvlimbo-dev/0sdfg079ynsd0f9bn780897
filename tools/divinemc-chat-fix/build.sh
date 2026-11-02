#!/bin/sh
set -eu
: "${JAVA:?}" "${ECJ:?}"
root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
out=${1:?output jar}
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
"$JAVA" -jar "$ECJ" -21 -encoding UTF-8 -proc:none -d "$tmp/classes" "$root/tools/divinemc-chat-fix/src/elytrix/EarlyThreadFix.java" "$root/tools/divinemc-chat-fix/test/org/bxteam/divinemc/config/DivineConfig.java" "$root/tools/divinemc-chat-fix/test/BootstrapTest.java" "$root/tools/divinemc-chat-fix/test/CustomLoaderTest.java"
OUT="$out" TEMP="$tmp" python3 - <<'PY'
import os,zipfile
from pathlib import Path
classes=Path(os.environ['TEMP'])/'classes/elytrix'
with zipfile.ZipFile(os.environ['OUT'],'x',zipfile.ZIP_DEFLATED) as z:
 z.writestr('META-INF/MANIFEST.MF','Manifest-Version: 1.0\r\nPremain-Class: elytrix.EarlyThreadFix\r\n\r\n')
 for f in sorted(classes.glob('*.class')):z.write(f,'elytrix/'+f.name)
PY
if "$JAVA" -Xverify:all -cp "$tmp/classes" BootstrapTest >"$tmp/without.log" 2>&1; then echo 'Expected failure without fix' >&2;exit 1;fi
grep -q 'ClassCastException' "$tmp/without.log"
"$JAVA" -Xverify:all -javaagent:"$out" -cp "$tmp/classes" BootstrapTest | tee "$tmp/with.log"
grep -q 'disabled virtual threads before server construction' "$tmp/with.log"
grep -q 'CHAT BOOTSTRAP OK' "$tmp/with.log"

"$JAVA" -Xverify:all -javaagent:"$out" -cp "$tmp/classes" CustomLoaderTest "$tmp/classes" | tee "$tmp/loader.log"
grep -q 'disabled virtual threads before server construction' "$tmp/loader.log"
grep -q 'CHAT BOOTSTRAP OK' "$tmp/loader.log"
