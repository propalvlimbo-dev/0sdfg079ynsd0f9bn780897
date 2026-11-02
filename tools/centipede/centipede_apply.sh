#!/usr/bin/env bash
# Elytrix — применить новую модель сороконожки целиком:
# блюпринт -> перегенерация ModelEngine -> пересборка РП-архива -> sha1 в ElytrixRP.
set -u
say()  { printf '\033[1m==> %s\033[0m\n' "$*"; }
ok()   { printf '    \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '    \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

SRV="${SRV:-/root/RW_GRIEF}"
SRC="${SRC:-/tmp/c}"
RPZIP="${RPZIP:-/root/RP/Elytrix-RP-1.21.zip}"
RELOAD="${RELOAD:-auto}"      # auto | no
WAIT="${WAIT:-90}"

ME="$SRV/plugins/ModelEngine"
GEN="$ME/resource pack"
BP="$ME/blueprints/elytrix_centipede.bbmodel"
TEX="$GEN/assets/modelengine/textures/entity/models/elytrix_centipede.png"
CFG="$SRV/plugins/ElytrixRP/config.yml"
STAMP=$(date +%Y%m%d-%H%M%S)

say "1/6  Проверки"
[ -d "$SRV" ] || die "нет каталога сервера: $SRV"
[ -d "$ME" ]  || die "нет ModelEngine: $ME"
[ -f "$SRC/blueprints/elytrix_centipede.bbmodel" ] || die "нет $SRC/blueprints/elytrix_centipede.bbmodel (распакуй архив в $SRC)"
[ -f "$RPZIP" ] || die "нет архива ресурспака: $RPZIP"
command -v python3 >/dev/null || die "нужен python3"
ok "сервер: $SRV"
ok "архив РП: $RPZIP ($(stat -c%s "$RPZIP") Б)"

say "2/6  Бэкап"
cp -a "$BP" "$BP.bak-$STAMP" && ok "блюпринт -> $(basename "$BP").bak-$STAMP"
[ -f "$TEX" ] && cp -a "$TEX" "$TEX.bak-$STAMP" && ok "текстура -> .bak-$STAMP"
[ -f "$CFG" ] && cp -a "$CFG" "$CFG.bak-$STAMP" && ok "ElytrixRP/config.yml -> .bak-$STAMP"
cp -a "$RPZIP" "$RPZIP.bak-$STAMP" && ok "архив РП -> $(basename "$RPZIP").bak-$STAMP"

say "3/6  Ставлю новый блюпринт и текстуру"
install -m 644 "$SRC/blueprints/elytrix_centipede.bbmodel" "$BP"
mkdir -p "$(dirname "$TEX")"
install -m 644 "$SRC/textures/elytrix_centipede.png" "$TEX"
ok "блюпринт $(sha256sum "$BP" | cut -c1-16)…"
ok "текстура $(sha256sum "$TEX" | cut -c1-16)…"

say "4/6  Перегенерация ModelEngine"
OLDHEAD="$GEN/assets/modelengine/models/elytrix_centipede/head.json"
BEFORE=$( [ -f "$OLDHEAD" ] && sha1sum "$OLDHEAD" | cut -d' ' -f1 || echo none )

send_cmd() {   # $1 = команда без слэша
    local cmd="$1" sent=0
    if command -v screen >/dev/null; then
        while read -r s; do
            [ -z "$s" ] && continue
            screen -S "$s" -p 0 -X stuff "$cmd"$'\n' 2>/dev/null && { ok "отправлено в screen/$s: $cmd"; sent=1; }
        done < <(screen -ls 2>/dev/null | sed -n 's/^[[:space:]]*\([0-9][0-9]*\.[^[:space:]]*\).*/\1/p')
    fi
    if [ "$sent" = 0 ] && command -v tmux >/dev/null; then
        while read -r s; do
            [ -z "$s" ] && continue
            tmux send-keys -t "$s" "$cmd" C-m 2>/dev/null && { ok "отправлено в tmux/$s: $cmd"; sent=1; }
        done < <(tmux ls 2>/dev/null | sed 's/:.*//')
    fi
    return $((1-sent))
}

if [ "$RELOAD" = no ]; then
    warn "перегенерация пропущена (RELOAD=no) — рассчитываю, что 'meg reload' уже выполнен"
else
    if send_cmd "meg reload"; then
        n=0
        while [ $n -lt "$WAIT" ]; do
            sleep 3; n=$((n+3))
            if [ -f "$OLDHEAD" ]; then
                now=$(sha1sum "$OLDHEAD" | cut -d' ' -f1)
                if [ "$now" != "$BEFORE" ] || grep -q 'skull_plate' "$OLDHEAD" 2>/dev/null; then
                    ok "ModelEngine пересобрал модель (${n} с)"; break
                fi
            fi
        done
        [ $n -ge "$WAIT" ] && warn "за $WAIT с изменений не увидел — продолжаю, но проверь консоль"
    else
        warn "консоль (screen/tmux) не найдена — введи в консоли сервера:  meg reload"
        warn "после этого запусти скрипт ещё раз с RELOAD=no"
    fi
fi
install -m 644 "$SRC/textures/elytrix_centipede.png" "$TEX"   # reload мог вернуть старую

say "5/6  Пересборка архива ресурспака"
PL=${TMPDIR:-/tmp}/cent_merge.py
cat > "$PL" <<'PYEOF'
import sys, zipfile, os, json
rpzip, gen = sys.argv[1], sys.argv[2]
PREFIX = ("assets/modelengine/models/elytrix_centipede/",
          "assets/modelengine/items/elytrix_centipede/",
          "assets/modelengine/textures/entity/models/elytrix_centipede.png")
OVR = "assets/minecraft/models/item/leather_horse_armor.json"

def norm(n): return n.lstrip("/")
src = {norm(os.path.relpath(os.path.join(dp, f), gen)): os.path.join(dp, f)
       for dp, _, fs in os.walk(gen) for f in fs}
have = sorted(k for k in src if k.startswith(PREFIX))
if not have:
    print("  в сгенерированном пакете нет файлов сороконожки — перегенерация не прошла"); sys.exit(2)

with zipfile.ZipFile(rpzip) as z:
    old = {os.path.basename(n)[:-5] for n in z.namelist()
           if n.startswith("assets/modelengine/models/elytrix_centipede/") and n.endswith(".json")}
new = {os.path.basename(n)[:-5] for n in have
       if "/models/elytrix_centipede/" in n and n.endswith(".json")}
print(f"  кости: было {sorted(old)}")
print(f"         стало {sorted(new)}")
gone = old - new
if gone:
    print(f"  пропали кости, на которые ссылается плагин: {sorted(gone)} — прерываю"); sys.exit(4)

tmp = rpzip + ".new"
kept = 0
with zipfile.ZipFile(rpzip) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
    for it in zin.infolist():
        n = norm(it.filename)
        if n.startswith(PREFIX) or n == "":
            continue
        zout.writestr(it, zin.read(it.filename)); kept += 1
    for n in have:
        zout.write(src[n], n)
print(f"  чужих файлов сохранено: {kept}; файлов сороконожки заменено: {len(have)}")
os.replace(tmp, rpzip)
PYEOF
python3 "$PL" "$RPZIP" "$GEN" || die "не смог пересобрать архив"
ok "архив пересобран: $RPZIP ($(stat -c%s "$RPZIP") Б)"

NEWSHA=$(sha1sum "$RPZIP" | cut -d' ' -f1)
say "6/6  sha1 для ElytrixRP"
if [ -f "$CFG" ]; then
    sed -i -E "s/^sha1:.*/sha1: \"$NEWSHA\"/" "$CFG"
    ok "sha1 в конфиге: $(grep '^sha1:' "$CFG")"
else
    warn "нет $CFG — обнови sha1 вручную: $NEWSHA"
fi
[ -d "$SRV/rp" ] && cp -a "$RPZIP" "$SRV/rp/$(basename "$RPZIP")" && ok "копия в $SRV/rp/"

echo
say "ИТОГО"
echo "    новый sha1 архива : $NEWSHA"
echo "    размер архива     : $(stat -c%s "$RPZIP") Б"
echo "    бэкапы с меткой   : $STAMP"
echo
echo "    Дальше:  /elytrixrp reload   (или перезапуск сервера), затем зайди в игру."
echo "    Игроки скачают пак заново: sha1 изменился."
