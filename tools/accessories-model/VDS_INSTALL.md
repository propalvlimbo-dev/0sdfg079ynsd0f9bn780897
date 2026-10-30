# Установка v19 на VDS

Один запуск, из любого места (нужен `unzip`, `curl`):

```bash
cd /root/RW_GRIEF && set -e && \
curl -fsSL -o /tmp/elytrix-v19.zip https://raw.githubusercontent.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/79172e0b5cc50036b9a2fb055887de54197ebd2b/elytrix-tentacles-v19.zip && \
B=/root/elytrix-backup-$(date +%Y%m%d-%H%M%S) && mkdir -p "$B" && \
for m in elytrix_kaneki_tentacles elytrix_kaneki_eyepatch; do \
  cp -a "plugins/ModelEngine/resource pack/assets/modelengine/models/$m" "$B/" 2>/dev/null || true; \
  cp -a "plugins/ModelEngine/resource pack/assets/modelengine/items/$m" "$B/" 2>/dev/null || true; \
  cp -a "plugins/ModelEngine/blueprints/$m.bbmodel" "$B/" 2>/dev/null || true; \
done && \
cp -a plugins/ElytrixRP/config.yml "$B/" 2>/dev/null || true && \
cp -a rp/Elytrix-RP-1.21.zip "$B/" 2>/dev/null || true && \
cp -a plugins/ElytrixFreakModel.jar "$B/" 2>/dev/null || true && \
rm -rf "plugins/ModelEngine/resource pack/assets/modelengine/models/elytrix_kaneki_tentacles" \
       "plugins/ModelEngine/resource pack/assets/modelengine/items/elytrix_kaneki_tentacles" \
       "plugins/ModelEngine/resource pack/assets/modelengine/models/elytrix_kaneki_eyepatch" \
       "plugins/ModelEngine/resource pack/assets/modelengine/items/elytrix_kaneki_eyepatch" && \
unzip -oq /tmp/elytrix-v19.zip -d /root/RW_GRIEF && \
cp -f rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip && \
chmod 644 /root/RP/Elytrix-RP-1.21.zip && \
sha1sum rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip
```

После этого — `restart` в консоли сервера.

Ожидаемый SHA-1: `7173523183d1e1f76d011702a350b44fadcd99bb` (оба пути должны совпасть).

Что ставится: **два** blueprint-а (щупальца и повязка), **57** JSON моделей +
57 item-definitions, текстуры обеих моделей, **две** иконки меню,
`ElytrixFreakModel.jar` с новой кнопкой, `rp/Elytrix-RP-1.21.zip`,
`plugins/ElytrixRP/config.yml` с новым SHA-1. Бэкап — в `/root/elytrix-backup-*`.

## Что нового в v19

- **Повязка Канэки.** Новый аксессуар `elytrix_kaneki_eyepatch`: белое полотно
  на **левый** глаз, тонкая лента по лбу и вокруг головы, узел с двумя концами
  за правым ухом. 11 кубов, 2 кости, без анимации — повязка не должна дёргаться.
- **В меню появился слот 15** (белый краситель с иконкой повязки). Слот 13 —
  нимб, слот 14 — щупальца, слот 30 снимает спину, слот 32 теперь снимает
  **голову** (и нимб, и повязку). Пункт «Снять с головы» заменил «Снять нимб».
- **Носится вместе со щупальцами.** Полотно садится на того же игрока вторым
  ActiveModel, поэтому «Канеки» = повязка + кагуне одновременно, а не «или-или».
- **Нимб и повязка взаимоисключающие** (один слот головы). Кто раньше выбрал
  нимб старым ключом `elytrixaccessories:halo`, у того нимб остаётся: новый
  ключ `elytrixaccessories:head` его перекрывает только когда выставлен.
- **Иконки меню перерисованы** в чистом пиксель-арте (без полупрозрачных
  пикселей), формат item-модели тот же, что в v18: `minecraft:item/generated`.

## Если что-то пошло не так

- Полотно висит в воздухе рядом с головой — не загрузился blueprint: проверьте
  `plugins/ModelEngine/blueprints/elytrix_kaneki_eyepatch.bbmodel` и лог
  `plugins/ModelEngine/` на строку с `elytrix_kaneki_eyepatch`.
- Слот 15 серый с чёрно-фиолетовой шахматкой — не подхватился ресурс-пак:
  сверьте SHA-1 выше и `plugins/ElytrixRP/config.yml`.
- Повязка не появляется вообще — проверьте, что в `plugins/` лежит именно
  `ElytrixFreakModel.jar` из этого архива (в нём есть
  `pw/elytrix/freakmodel/AccessoryController$PatchRig.class`).
- Откат: скопировать файлы из `/root/elytrix-backup-*` обратно и `restart`.
