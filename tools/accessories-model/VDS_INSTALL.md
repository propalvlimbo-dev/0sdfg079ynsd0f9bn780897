# Установка v12 на VDS

Один запуск, из любого места (нужен `unzip`, `curl`):

```bash
cd /root/RW_GRIEF && set -e && \
curl -fsSL -o /tmp/elytrix-v12.zip https://raw.githubusercontent.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/3a6e4a93144b2bb0520996c8577ba90be38c9baa/elytrix-tentacles-v12.zip && \
B=/root/elytrix-backup-$(date +%Y%m%d-%H%M%S) && mkdir -p "$B" && \
cp -a "plugins/ModelEngine/resource pack/assets/modelengine/models/elytrix_kaneki_tentacles" "$B/" 2>/dev/null || true && \
cp -a plugins/ModelEngine/blueprints/elytrix_kaneki_tentacles.bbmodel "$B/" 2>/dev/null || true && \
cp -a plugins/ElytrixRP/config.yml "$B/" 2>/dev/null || true && \
cp -a rp/Elytrix-RP-1.21.zip "$B/" 2>/dev/null || true && \
cp -a plugins/ElytrixFreakModel.jar "$B/" 2>/dev/null || true && \
rm -rf "plugins/ModelEngine/resource pack/assets/modelengine/models/elytrix_kaneki_tentacles" \
       "plugins/ModelEngine/resource pack/assets/modelengine/items/elytrix_kaneki_tentacles" && \
unzip -oq /tmp/elytrix-v12.zip -d /root/RW_GRIEF && \
cp -f rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip && \
chmod 644 /root/RP/Elytrix-RP-1.21.zip && \
sha1sum rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip
```

После этого — `restart` в консоли сервера.

Ожидаемый SHA-1: `189d09dbeb8c64cd7b0c904bdbe26dfa01de9170` (оба пути должны совпасть).

Что ставится: blueprint, **31** JSON моделей + 31 item-definitions + текстура кагуне,
иконка меню, `ElytrixFreakModel.jar` (свой спек щупалец вместо копии крыльев),
`rp/Elytrix-RP-1.21.zip`, `plugins/ElytrixRP/config.yml` с новым SHA-1.
Бэкап — в `/root/elytrix-backup-*`.

Старые файлы модели удаляются до распаковки: у v10 другой набор костей
(8/8/7/7 + узел), без `rm -rf` в паке остались бы файлы
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
- Форма как на референсе: лучи выходят из спины (z = 2.3), обходят корпус снаружи
  и заканчиваются впереди тела (z = −5.8). Верхняя пара на y ≈ 21, нижняя на y ≈ 12.
  Габарит 27.3 × 9.2 × 8.1 единицы (≈1.7 × 0.58 × 0.51 блока).
