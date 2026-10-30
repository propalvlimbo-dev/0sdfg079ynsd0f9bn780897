# Установка v15 на VDS

Один запуск, из любого места (нужен `unzip`, `curl`):

```bash
cd /root/RW_GRIEF && set -e && \
curl -fsSL -o /tmp/elytrix-v15.zip https://raw.githubusercontent.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/8a72d6164581bbd191996b9d7e280ab48537beca/elytrix-tentacles-v15.zip && \
B=/root/elytrix-backup-$(date +%Y%m%d-%H%M%S) && mkdir -p "$B" && \
cp -a "plugins/ModelEngine/resource pack/assets/modelengine/models/elytrix_kaneki_tentacles" "$B/" 2>/dev/null || true && \
cp -a "plugins/ModelEngine/resource pack/assets/modelengine/items/elytrix_kaneki_tentacles" "$B/" 2>/dev/null || true && \
cp -a plugins/ModelEngine/blueprints/elytrix_kaneki_tentacles.bbmodel "$B/" 2>/dev/null || true && \
cp -a plugins/ElytrixRP/config.yml "$B/" 2>/dev/null || true && \
cp -a rp/Elytrix-RP-1.21.zip "$B/" 2>/dev/null || true && \
cp -a plugins/ElytrixFreakModel.jar "$B/" 2>/dev/null || true && \
rm -rf "plugins/ModelEngine/resource pack/assets/modelengine/models/elytrix_kaneki_tentacles" \
       "plugins/ModelEngine/resource pack/assets/modelengine/items/elytrix_kaneki_tentacles" && \
unzip -oq /tmp/elytrix-v15.zip -d /root/RW_GRIEF && \
cp -f rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip && \
chmod 644 /root/RP/Elytrix-RP-1.21.zip && \
sha1sum rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip
```

После этого — `restart` в консоли сервера.

Ожидаемый SHA-1: `d3842bce95561d50f6c50e402f241f73dafc7e77` (оба пути должны совпасть).

Что ставится: blueprint, **41** JSON модель + 41 item-definition + текстура кагуне,
иконка меню, `ElytrixFreakModel.jar`, `rp/Elytrix-RP-1.21.zip`,
`plugins/ElytrixRP/config.yml` с новым SHA-1. Бэкап — в `/root/elytrix-backup-*`.

Старые файлы модели удаляются до распаковки: у v15 другой набор костей
(10/10/10/10 + узел), без `rm -rf` в паке остались бы файлы прошлой версии.

## Что изменилось в рендере

- **Форма по референсу: четыре «руки» из одной точки на спине.** Каждая выходит
  из позвоночника по диагонали, имеет два локтя, уходит в сторону и заканчивается
  поднятым кончиком. Верхняя пара идёт над лопатками, нижняя — под рёбрами.
- **Вперёд почти не уходит.** Боковой разлёт 34.4 единицы, вперёд всего 1.9
  (у v14 было 15.6 вперёд — отсюда и «слишком ровно идут»). Глубина 4.1.
- **Рука, а не шило:** толщина 4.2 в корне держится до 62% длины и только потом
  сходит в 0.34; в прошлой версии она падала уже с 35%.
- Узел на спине сжат до ширины ладони — руки выходят из одной узкой точки,
  а не из красного рюкзака.
- В модели нет клипа `idle`: `WornAngelRig` переигрывает клип слота спины, а
  ключи кадров абсолютные — отсюда раньше были «огромные C» вокруг тела.
  Форма — это рест-поза.
- Спек свой: `elytrix_kaneki_tentacles` (масштаб 1.0, нулевые офсеты, интерполяция 1).
