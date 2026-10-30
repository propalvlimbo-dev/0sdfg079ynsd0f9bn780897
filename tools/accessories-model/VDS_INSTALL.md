# Установка v8 на VDS

Один запуск, из любого места (нужен `unzip`, `curl`):

```bash
cd /root/RW_GRIEF && set -e && \
curl -fsSL -o /tmp/elytrix-v8.zip https://raw.githubusercontent.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/632117c26631f140e74ed69a5d612c25111655ba/elytrix-tentacles-v8.zip && \
B=/root/elytrix-backup-$(date +%Y%m%d-%H%M%S) && mkdir -p "$B" && \
cp -a "plugins/ModelEngine/resource pack/assets/modelengine/models/elytrix_kaneki_tentacles" "$B/" 2>/dev/null || true && \
cp -a plugins/ModelEngine/blueprints/elytrix_kaneki_tentacles.bbmodel "$B/" 2>/dev/null || true && \
cp -a plugins/ElytrixRP/config.yml "$B/" 2>/dev/null || true && \
cp -a rp/Elytrix-RP-1.21.zip "$B/" 2>/dev/null || true && \
rm -rf "plugins/ModelEngine/resource pack/assets/modelengine/models/elytrix_kaneki_tentacles" \
       "plugins/ModelEngine/resource pack/assets/modelengine/items/elytrix_kaneki_tentacles" && \
unzip -oq /tmp/elytrix-v8.zip -d /root/RW_GRIEF && \
cp -f rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip && \
chmod 644 /root/RP/Elytrix-RP-1.21.zip && \
sha1sum rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip
```

После этого — `restart` в консоли сервера.

Ожидаемый SHA-1: `8d0f7f9c05538e7f221d58c91d26f3e2edbadc29` (оба пути должны совпасть).

Что ставится: blueprint, **40** JSON моделей + 40 item-definitions + текстура щупалец,
иконка меню (`assets/reallyworld/...kaneki_tentacles_icon`), `ElytrixFreakModel.jar`,
`rp/Elytrix-RP-1.21.zip`, `plugins/ElytrixRP/config.yml` с новым SHA-1.
Бэкап прежних файлов лежит в `/root/elytrix-backup-*`.

Старые файлы модели удаляются до распаковки: у v7 было 28 костей (`a`…`g`), у v8 —
39 костей + узел (`a`…`j`), и без `rm -rf` в паке остались бы оба набора.
