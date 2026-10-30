# Установка v20 на VDS

Один запуск, из любого места (нужен `unzip`, `curl`):

```bash
cd /root/RW_GRIEF && set -e && \
curl -fsSL -o /tmp/elytrix-v20.zip https://raw.githubusercontent.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/779e79b4d9537dee68c7feb1dd7835cc5b4831d1/elytrix-tentacles-v20.zip && \
B=/root/elytrix-backup-$(date +%Y%m%d-%H%M%S) && mkdir -p "$B" && \
cp -a plugins/ElytrixFreakModel.jar "$B/" 2>/dev/null || true && \
cp -a plugins/ElytrixRP/config.yml "$B/" 2>/dev/null || true && \
cp -a rp/Elytrix-RP-1.21.zip "$B/" 2>/dev/null || true && \
unzip -oq /tmp/elytrix-v20.zip -d /root/RW_GRIEF && \
cp -f rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip && \
chmod 644 /root/RP/Elytrix-RP-1.21.zip && \
sha1sum rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip
```

После этого — `restart` в консоли сервера.

Ожидаемый SHA-1: `7173523183d1e1f76d011702a350b44fadcd99bb` — **не менялся с v19**,
пак тот же самый. Если строка совпала, ресурспак переустанавливать не нужно,
меняется только `plugins/ElytrixFreakModel.jar`.

## Что нового в v20

- **Кагуне больше не отстаёт и не дёргается.** В стоковой сборке весь риг
  (позиция, поворот тела, анимация) обновлялся только раз в 4 тика — 5 раз
  в секунду. Отсюда были рывки при ходьбе и «подлёт» к спине после резкого
  поворота. Байткод `tickWornAngelRigs` пропатчен: `globalTickCounter % 4`
  превращён в `% 1`, то есть риг синхронизируется **каждый тик (20 Гц)**.
  Крылья и нимб это тоже ускоряет — они перестают отставать так же.
- **«Назад» — иконка из ресурспака**, как в `/menu`: это `ARROW` с
  `custom_model_data: 10002` (в паке это `reallyworld:item/left`), а не пустая
  стрелка, которую рисовал сам плагин.
- **Клик — переключатель.** Один клик надевает, второй снимает. Надетый
  аксессуар помечен в лоре строкой «● Сейчас надето», и меню перерисовывается
  сразу после клика.
- **Одна кнопка «Снять всё»** (слот 30) вместо двух прежних: снимает и спину,
  и голову.
- **Доступ для доната `media`.** Вместо одного `elytrixaccessories.admin`
  плагин теперь принимает и `elytrixaccessories.use`. При старте он сам
  выполняет в консоли:
  ```
  lp group media permission set elytrixaccessories.use true
  ```
  то есть группа `media` получает доступ без ручных команд. Если LuckPerms нет,
  команда запрещена или он ещё грузился в этот момент — плагин повторит попытку
  при первом открытии меню; вручную это та же команда в консоли.

## Если что-то пошло не так

- Кнопки не переключаются — проверьте, что в `plugins/` лежит именно
  `ElytrixFreakModel.jar` из этого архива (в нём есть
  `pw/elytrix/freakmodel/AccessoryController$PatchRig.class` и пропатченный
  `ElytrixFreakModelPlugin`).
- Доступ у `media` не появился — выполните в консоли
  `lp group media permission set elytrixaccessories.use true` и проверьте
  `lp group media info`.
- Кагуне всё ещё отстаёт — значит, патч не применился: в логе при старте не
  должно быть ошибок от ElytrixFreakModel.
- Откат: скопировать `ElytrixFreakModel.jar` из `/root/elytrix-backup-*`
  обратно и `restart`.
