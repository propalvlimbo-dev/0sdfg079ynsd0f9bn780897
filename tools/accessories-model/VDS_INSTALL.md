# Установка v13 на VDS

Один запуск, из любого места (нужен `unzip`, `curl`):

```bash
cd /root/RW_GRIEF && set -e && \
curl -fsSL -o /tmp/elytrix-v13.zip https://raw.githubusercontent.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/ed49d9fdbcd6ac5910401b6ebb54ecc48f9af4c3/elytrix-tentacles-v13.zip && \
B=/root/elytrix-backup-$(date +%Y%m%d-%H%M%S) && mkdir -p "$B" && \
cp -a "plugins/ModelEngine/resource pack/assets/modelengine/models/elytrix_kaneki_tentacles" "$B/" 2>/dev/null || true && \
cp -a plugins/ModelEngine/blueprints/elytrix_kaneki_tentacles.bbmodel "$B/" 2>/dev/null || true && \
cp -a plugins/ElytrixRP/config.yml "$B/" 2>/dev/null || true && \
cp -a rp/Elytrix-RP-1.21.zip "$B/" 2>/dev/null || true && \
cp -a plugins/ElytrixFreakModel.jar "$B/" 2>/dev/null || true && \
rm -rf "plugins/ModelEngine/resource pack/assets/modelengine/models/elytrix_kaneki_tentacles" \
       "plugins/ModelEngine/resource pack/assets/modelengine/items/elytrix_kaneki_tentacles" && \
unzip -oq /tmp/elytrix-v13.zip -d /root/RW_GRIEF && \
cp -f rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip && \
chmod 644 /root/RP/Elytrix-RP-1.21.zip && \
sha1sum rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip
```

После этого — `restart` в консоли сервера.

Ожидаемый SHA-1: `7939972bd45696133e677d622cf6dd5b9f90248e` (оба пути должны совпасть).

Что ставится: blueprint, **37** JSON моделей + 37 item-definitions + текстура кагуне,
иконка меню, `ElytrixFreakModel.jar` (свой спек щупалец вместо копии крыльев),
`rp/Elytrix-RP-1.21.zip`, `plugins/ElytrixRP/config.yml` с новым SHA-1.
Бэкап — в `/root/elytrix-backup-*`.

Старые файлы модели удаляются до распаковки: у v10 другой набор костей
(9/9/9/9 + узел), без `rm -rf` в паке остались бы файлы
прошлой версии.

## Что изменилось в рендере

- В модели больше нет клипа `idle`. `ElytrixFreakModel` держит в слоте спины
  модель через `WornAngelRig` и постоянно переигрывает её клип; ключи кадров
  абсолютные, и любое расхождение знака с решённой рест-позой удваивало изгиб
  каждой кости — отсюда и были «огромные C» вокруг тела. Теперь форма — это
  рест-поза, переигрывать нечего.
- У щупалец свой спек `elytrix_kaneki_tentacles` (`AccessoryController.kaneki`):
  масштаб 1.0, нулевые офсеты, интерполяция 1. Если в `config.yml` появится
  модель с таким id, плагин возьмёт её настройки вместо встроенных.
- Тонкие длинные хвосты по эскизу: изгиб сконцентрирован у корня, дальше почти
  прямая линия. Толщина 3.6 в корне (было 5.6) и 0.3 на конце. Размах 44.1 единицы
  (2.76 блока), высота 4.4, глубина 6.6. Верхняя пара выходит на y ≈ 17.5, нижняя на
  y ≈ 15.9, к концам расходятся до 17.3 и 14.1.
