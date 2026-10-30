# Установка v11 на VDS

Один запуск, из любого места (нужен `unzip`, `curl`):

```bash
cd /root/RW_GRIEF && set -e && \
curl -fsSL -o /tmp/elytrix-v11.zip https://raw.githubusercontent.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/f6dacfef0d576f459941cc16d872a55c99ccd794/elytrix-tentacles-v11.zip && \
B=/root/elytrix-backup-$(date +%Y%m%d-%H%M%S) && mkdir -p "$B" && \
cp -a "plugins/ModelEngine/resource pack/assets/modelengine/models/elytrix_kaneki_tentacles" "$B/" 2>/dev/null || true && \
cp -a plugins/ModelEngine/blueprints/elytrix_kaneki_tentacles.bbmodel "$B/" 2>/dev/null || true && \
cp -a plugins/ElytrixRP/config.yml "$B/" 2>/dev/null || true && \
cp -a rp/Elytrix-RP-1.21.zip "$B/" 2>/dev/null || true && \
cp -a plugins/ElytrixFreakModel.jar "$B/" 2>/dev/null || true && \
rm -rf "plugins/ModelEngine/resource pack/assets/modelengine/models/elytrix_kaneki_tentacles" \
       "plugins/ModelEngine/resource pack/assets/modelengine/items/elytrix_kaneki_tentacles" && \
unzip -oq /tmp/elytrix-v11.zip -d /root/RW_GRIEF && \
cp -f rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip && \
chmod 644 /root/RP/Elytrix-RP-1.21.zip && \
sha1sum rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip
```

После этого — `restart` в консоли сервера.

Ожидаемый SHA-1: `4723630af082b2aece4003359f73b65396108e2e` (оба пути должны совпасть).

Что ставится: blueprint, **51** JSON моделей + 51 item-definitions + текстура кагуне,
иконка меню, `ElytrixFreakModel.jar` (свой спек щупалец вместо копии крыльев),
`rp/Elytrix-RP-1.21.zip`, `plugins/ElytrixRP/config.yml` с новым SHA-1.
Бэкап — в `/root/elytrix-backup-*`.

Старые файлы модели удаляются до распаковки: у v10 другой набор костей
(13/13/12/12 + узел, у v10 было 8/8/6/6), без `rm -rf` в паке остались бы файлы
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
- Веер стал вдвое больше: 2.9 × 1.74 блока, вершины выше головы (y 44.6) и за плечами
  (x ±23.3). Глубина — 8 единиц за спиной (z 2.4 → 10.5).
