# Установка v21 на VDS

v21 — это **только `ElytrixFreakModel.jar`**: ресурспак, blueprint-ы и ассеты не менялись
(SHA-1 пака остаётся `7173523183d1e1f76d011702a350b44fadcd99bb`).

Одна команда, из любого места:

```bash
cd /root/RW_GRIEF && set -e && \
curl -fsSL -o /tmp/elytrix-v21.zip https://raw.githubusercontent.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/ecdad4901e9a778705879550ecabe88e441f438a/elytrix-tentacles-v21.zip && \
B=/root/elytrix-backup-$(date +%Y%m%d-%H%M%S) && mkdir -p "$B" && \
cp -a plugins/ElytrixFreakModel.jar "$B/" && \
unzip -oq /tmp/elytrix-v21.zip plugins/ElytrixFreakModel.jar -d /root/RW_GRIEF && \
sha256sum plugins/ElytrixFreakModel.jar
```

Ожидаемый SHA-256 jar: `096ecb999a9760704618f9e24b124f242776d97a12a86dd33c6766d54cd8f401`.
Бэкап старого jar — в `/root/elytrix-backup-*`.

После этого — `restart` в консоли сервера.

## Что чинит v21

`/аксессуары` отвечал `Cannot execute command 'аксессуары' ... plugin is disabled`:
плагин падал на `onEnable`, и вместе с меню умирали крылья, нимб, кагуне и повязка.
Код аксессуаров подключается в самом конце `onEnable`, поэтому любое исключение
оттуда выключало весь плагин.

- `AccessoryController.install()` теперь ловит `Throwable`, пишет предупреждение
  в лог и **не роняет плагин**; если команда `accessories` не найдена — просто
  логирует это.
- `tickEyepatch` защищён от повторов: одна ошибка на игрока, без спама 20 раз
  в секунду.
- Выдача прав LuckPerms тоже не может уронить включение.

Если после `restart` в логе всё ещё есть `plugin is disabled` — значит причина не
в коде аксессуаров, а в самом включении плагина (чаще всего не поднялся
`ModelEngine`). Тогда нужен лог:

```bash
grep -n -B2 -A25 "ElytrixFreakModel" /root/RW_GRIEF/logs/latest.log | tail -60
```

## Откат

```bash
cp -f /root/elytrix-backup-*/ElytrixFreakModel.jar /root/RW_GRIEF/plugins/ && restart
```
