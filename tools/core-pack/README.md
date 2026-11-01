# Elytrix — пак ядра и конфигов

Снимок рабочей конфигурации сервера: ядро Leaf 1.21.11 build 179, `start.sh`,
все конфиги ядра в том виде, в котором сервер сейчас держит 20 TPS, и скрипты
диагностики лагов.

Собран `2026-11-01`. Держи этот архив как точку возврата: если что-то пойдёт не
так, из него восстанавливается всё, кроме миров и плагинов.

## Что внутри

```
elytrix-server-pack-v1/
├── README.md              этот файл
├── download-core.sh       скачать ядро Leaf 1.21.11-179 (проверяет SHA-256)
├── apply.sh               разложить конфиги в каталог сервера (с бэкапами)
├── backup-server.sh       снять полный бэкап живого сервера в один tar.gz
├── start.sh               запуск: G1, heap 60% RAM, gc.log, автоперезапуск
├── server.properties      эталон значений (не копируется целиком, для сверки)
├── configs/
│   ├── bukkit.yml
│   ├── spigot.yml
│   ├── pufferfish.yml
│   ├── purpur.yml
│   └── config/
│       ├── paper-global.yml
│       ├── paper-world-defaults.yml
│       ├── leaf-global.yml
│       ├── gale-global.yml
│       └── gale-world-defaults.yml
└── tools/lagfix/          диагностика: jfr30.sh, spark30.sh, lagdoctor.sh и др.
```

## Как развернуть с нуля

```bash
unzip elytrix-server-pack-v1.zip -d /root/pack
mkdir -p /root/RW_GRIEF && cd /root/RW_GRIEF

bash /root/pack/elytrix-server-pack-v1/download-core.sh /root/RW_GRIEF
bash /root/pack/elytrix-server-pack-v1/apply.sh /root/RW_GRIEF
cp /root/pack/elytrix-server-pack-v1/start.sh /root/RW_GRIEF/start.sh && chmod +x /root/RW_GRIEF/start.sh

# плагины и миры переносишь свои, потом:
cd /root/RW_GRIEF && bash start.sh
```

## Как снять бэкап того, что уже работает

```bash
bash backup-server.sh /root/RW_GRIEF
```

Получится `/root/RW_GRIEF-backup-20261101-1430.tar.gz` — внутри ядро, конфиги,
`start.sh`, каталог `plugins/` целиком (со конфигами плагинов) и `logs/latest.log`.
Миры по умолчанию не входят; если нужны:

```bash
WITH_WORLDS=1 bash backup-server.sh /root/RW_GRIEF
```

Скачать к себе:

```bash
scp root@<адрес-сервера>:/root/RW_GRIEF-backup-*.tar.gz .
```

## Ядро

| | |
|---|---|
| Сборка | Leaf **1.21.11 build 179** |
| Ссылка | https://github.com/Winds-Studio/Leaf/releases/download/ver-1.21.11/leaf-1.21.11-179.jar |
| Размер | 83 953 995 байт |
| SHA-256 | `5da79782215c1a25edcd7c73b3523b7ecb7f4b86dc8a5846a176ed69bc2cd020` |

`download-core.sh` сверяет и размер, и SHA-256: битый или подменённый файл он
не поставит.

## Что настроено и почему (по замерам JFR)

Каждое значение появилось не из общих советов, а из профиля этого сервера.

| Что | Значение | Почему |
|---|---|---|
| GC | **G1**, цель паузы 200 мс | ZGC на 3 ядрах жег ядра конкурентными циклами по 900 мс |
| `sync-chunk-writes` | `false` | без этого каждая запись чанка идёт с fsync — секундные тики |
| `view-distance` / `simulation-distance` | 4 / 4 | видно 4 чанка — тикать 10 незачем (было 10) |
| `simulation-distance` в spigot.yml | 4 | per-world значение перекрывает server.properties |
| блок-сущности | 17.5% главного потока | `tickBlockEntities` + ульи + `getBlockState` в тикающих чанках |
| `max-auto-save-chunks-per-tick` | 6 | автосейв не должен влезать в один тик |
| `ticks-per.autosave` | 18000 | сейв раз в 15 минут, а не каждые 5 |
| `entity-activation-range` | animals 12, monsters 20, villagers 12, misc/water 8 | ИИ мобов вдалеке не нужен |
| `merge-radius` | item 3.5, exp 5.0 | меньше предметов — меньше тиков |
| `item-despawn-rate` | 3600 | дроп живёт 3 минуты, а не 5 |
| `tick-inactive-villagers` | false | деревни без игрока не тикают |
| `hopper-transfer/check` | 16 / 8 | воронки — главный источник `tickBlockEntities` |
| `hopper-can-load-chunks` | false | воронка не грузит чанк |
| хопперы/счётчики в `paper-world-defaults` | hopper cooldown, tick-rates | реже проверки контейнеров и сенсоров |

## Чего тут нет

* **Миров** — они тяжёлые, бэкапь их отдельно (`WITH_WORLDS=1`).
* **Плагинов** — `plugins/` переносится как есть; конфиги плагинов в пак не
  входят, чтобы не тащить лишнее.
* **`server.properties` твоего сервера** — в паке только эталон значений и
  правка одного ключа (`sync-chunk-writes`). Порты, `motd`, `online-mode`
  остаются твоими.

## Диагностика (если снова начнёт лагать)

```bash
bash tools/lagfix/jfr30.sh /root/RW_GRIEF now 120     # снять и разобрать 2 минуты
bash tools/lagfix/jfr30.sh /root/RW_GRIEF spikes 10   # где именно всплески
bash tools/lagfix/jfr30.sh /root/RW_GRIEF waits 50    # кто ЖДАЛ: диск, сокет, лок
bash tools/lagfix/jfr30.sh /root/RW_GRIEF tasks       # кто заваливает планировщик
bash tools/lagfix/jfr30.sh /root/RW_GRIEF psend       # кто слушает исходящие пакеты
```

И в консоли сервера — ловушка на медленные тики (не мешает, собирает только их):

```
/spark profiler start --only-ticks-over 100 --timeout 3600
```
