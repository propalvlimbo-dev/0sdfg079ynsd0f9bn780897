# Установка v17 на VDS

Один запуск, из любого места (нужен `unzip`, `curl`):

```bash
cd /root/RW_GRIEF && set -e && \
curl -fsSL -o /tmp/elytrix-v17.zip https://raw.githubusercontent.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/aa98b39e2e783f6eda52a8cf2ceec9288dd97d20/elytrix-tentacles-v17.zip && \
B=/root/elytrix-backup-$(date +%Y%m%d-%H%M%S) && mkdir -p "$B" && \
cp -a "plugins/ModelEngine/resource pack/assets/modelengine/models/elytrix_kaneki_tentacles" "$B/" 2>/dev/null || true && \
cp -a "plugins/ModelEngine/resource pack/assets/modelengine/items/elytrix_kaneki_tentacles" "$B/" 2>/dev/null || true && \
cp -a plugins/ModelEngine/blueprints/elytrix_kaneki_tentacles.bbmodel "$B/" 2>/dev/null || true && \
cp -a plugins/ElytrixRP/config.yml "$B/" 2>/dev/null || true && \
cp -a rp/Elytrix-RP-1.21.zip "$B/" 2>/dev/null || true && \
cp -a plugins/ElytrixFreakModel.jar "$B/" 2>/dev/null || true && \
rm -rf "plugins/ModelEngine/resource pack/assets/modelengine/models/elytrix_kaneki_tentacles" \
       "plugins/ModelEngine/resource pack/assets/modelengine/items/elytrix_kaneki_tentacles" && \
unzip -oq /tmp/elytrix-v17.zip -d /root/RW_GRIEF && \
cp -f rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip && \
chmod 644 /root/RP/Elytrix-RP-1.21.zip && \
sha1sum rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip
```

После этого — `restart` в консоли сервера.

Ожидаемый SHA-1: `b1d501b64fbccface6b3b9585188964c8f116f7f` (оба пути должны совпасть).

Что ставится: blueprint, **53** JSON модели + 53 item-definition + текстура кагуне,
иконка меню, `ElytrixFreakModel.jar`, `rp/Elytrix-RP-1.21.zip`,
`plugins/ElytrixRP/config.yml` с новым SHA-1. Бэкап — в `/root/elytrix-backup-*`.

## Что изменилось в v17

- **Длиннее.** Размах рук вырос с 24.8 до 36.8 единицы: кончики доходят до
  x = ±18.4 (было ±12.4), на каждую руку 13 костей вместо 9.
- **Тоньше.** Толщина в теле 3.0 против 4.8 — на 37% меньше. Конец по-прежнему
  тупой (66% толщины), без «писюлек».
- **Заворот вперёд.** Рука выходит из спины, выгибается назад до z = +6.4 и затем
  заворачивает вперёд до z = −3.0 — то есть 9.4 единицы хода в сторону взгляда.
  Раньше кончик только висел за спиной и вперёд не шёл.
- Размер 36.8 × 13.4 × 9.4 единицы (2.3 × 0.84 × 0.59 блока), 108 кубов / 53 модели.
