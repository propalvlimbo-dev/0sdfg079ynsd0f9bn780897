# Установка v18 на VDS

Один запуск, из любого места (нужен `unzip`, `curl`):

```bash
cd /root/RW_GRIEF && set -e && \
curl -fsSL -o /tmp/elytrix-v18.zip https://raw.githubusercontent.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/d84cb24e89ee8d05fbbbf2278de33852150037b2/elytrix-tentacles-v18.zip && \
B=/root/elytrix-backup-$(date +%Y%m%d-%H%M%S) && mkdir -p "$B" && \
cp -a "plugins/ModelEngine/resource pack/assets/modelengine/models/elytrix_kaneki_tentacles" "$B/" 2>/dev/null || true && \
cp -a "plugins/ModelEngine/resource pack/assets/modelengine/items/elytrix_kaneki_tentacles" "$B/" 2>/dev/null || true && \
cp -a plugins/ModelEngine/blueprints/elytrix_kaneki_tentacles.bbmodel "$B/" 2>/dev/null || true && \
cp -a plugins/ElytrixRP/config.yml "$B/" 2>/dev/null || true && \
cp -a rp/Elytrix-RP-1.21.zip "$B/" 2>/dev/null || true && \
cp -a plugins/ElytrixFreakModel.jar "$B/" 2>/dev/null || true && \
rm -rf "plugins/ModelEngine/resource pack/assets/modelengine/models/elytrix_kaneki_tentacles" \
       "plugins/ModelEngine/resource pack/assets/modelengine/items/elytrix_kaneki_tentacles" && \
unzip -oq /tmp/elytrix-v18.zip -d /root/RW_GRIEF && \
cp -f rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip && \
chmod 644 /root/RP/Elytrix-RP-1.21.zip && \
sha1sum rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip
```

После этого — `restart` в консоли сервера.

Ожидаемый SHA-1: `19e05affc9ef9a31e4d81dcff5ab4fa7912f41ca` (оба пути должны совпасть).

Что ставится: blueprint, **55** JSON моделей + 55 item-definitions + текстура кагуне,
иконка меню, `ElytrixFreakModel.jar`, `rp/Elytrix-RP-1.21.zip`,
`plugins/ElytrixRP/config.yml` с новым SHA-1. Бэкап — в `/root/elytrix-backup-*`.

## Что изменилось в v18

- **Верх и низ отличаются.** Нижняя пара больше не зеркало верхней: она уходит
  дальше (x = ±19.6 против ±18.4), глубже (z до 6.9 против 6.4) и она тоньше
  (2.75 против 3.0). На глаз это разные руки, а не отражение.
- **Анимация.** В blueprint появился клип `idle` (4 секунды, петля):
  каждая рука ходит вверх-вниз и вперёд-назад, четыре руки в разных фазах,
  амплитуда ±7° на кончике и ±1° у корня.
- **Почему клип не сломает форму.** В ModelEngine 4.1 поворот из клипа
  прибавляется к рест-повороту (`bone.localRotation.add(key)`), поэтому в ключи
  записаны только **дeltas** вокруг нуля. В v9 в ключи были записаны абсолютные
  углы — отсюда и были «огромные C» вокруг тела.

Размер 39.2 × 13.9 × 10.0 единицы (2.45 × 0.87 × 0.63 блока), 112 кубов / 55 моделей,
13/13/14/14 костей.
