# Установка v16 на VDS

Один запуск, из любого места (нужен `unzip`, `curl`):

```bash
cd /root/RW_GRIEF && set -e && \
curl -fsSL -o /tmp/elytrix-v16.zip https://raw.githubusercontent.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/c5b2ac984a8bb3a5a93f673b38b0394a5e9abf8f/elytrix-tentacles-v16.zip && \
B=/root/elytrix-backup-$(date +%Y%m%d-%H%M%S) && mkdir -p "$B" && \
cp -a "plugins/ModelEngine/resource pack/assets/modelengine/models/elytrix_kaneki_tentacles" "$B/" 2>/dev/null || true && \
cp -a "plugins/ModelEngine/resource pack/assets/modelengine/items/elytrix_kaneki_tentacles" "$B/" 2>/dev/null || true && \
cp -a plugins/ModelEngine/blueprints/elytrix_kaneki_tentacles.bbmodel "$B/" 2>/dev/null || true && \
cp -a plugins/ElytrixRP/config.yml "$B/" 2>/dev/null || true && \
cp -a rp/Elytrix-RP-1.21.zip "$B/" 2>/dev/null || true && \
cp -a plugins/ElytrixFreakModel.jar "$B/" 2>/dev/null || true && \
rm -rf "plugins/ModelEngine/resource pack/assets/modelengine/models/elytrix_kaneki_tentacles" \
       "plugins/ModelEngine/resource pack/assets/modelengine/items/elytrix_kaneki_tentacles" && \
unzip -oq /tmp/elytrix-v16.zip -d /root/RW_GRIEF && \
cp -f rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip && \
chmod 644 /root/RP/Elytrix-RP-1.21.zip && \
sha1sum rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip
```

После этого — `restart` в консоли сервера.

Ожидаемый SHA-1: `6f578602cd0785d6300e1c9dc5eb39c92edfc47f` (оба пути должны совпасть).

Что ставится: blueprint, **33** JSON модели + 33 item-definition + текстура кагуне,
иконка меню, `ElytrixFreakModel.jar`, `rp/Elytrix-RP-1.21.zip`,
`plugins/ElytrixRP/config.yml` с новым SHA-1. Бэкап — в `/root/elytrix-backup-*`.

## Что изменилось по скринам

- **«Писюльки в конце»** — конец руки теперь толстый и обрывается тупым срезом.
  Раньше последняя кость за один шаг прыгала с 4.58 до 2.50 — это и была игла.
  Теперь толщина 4.8 держится до 58% длины и плавно сходит к 2.8.
- **«Со стороны плохо выглядит»** — руки уходят не только в стороны, но и назад
  от спины (z от 2.2 до 9.0), поэтому сбоку они висят за игроком, а не сбиваются
  в один ком.
- **«В притык сильно»** — корень руки уже самой руки (55%), поэтому четыре руки
  выходят из одной точки с зазором, а не слипаются в красную плиту.
- **«Не идут со спины, лежат на спине»** — каждая кость получает +Z: кончик
  оказывается на 7 единиц позади поверхности спины, рука явно выходит из неё.

Размер 24.8 × 13.9 × 6.8 единицы (1.55 × 0.87 × 0.43 блока), 68 кубов / 33 модели,
9/9/9/9 костей.
