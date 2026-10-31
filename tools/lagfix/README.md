# Elytrix — lagfix v1

Пакет закрывает то, что видно в профиле spark, и не трогает ничего лишнего.
Все изменения делаются с бэкапами вида `*.bak-lagfix-<дата>`, повторный запуск
безопасен.

## Что чинит

| Причина из профиля | Что делает пакет |
|---|---|
| BLib падает в `Version.<clinit>` на 1.21.11 | добавляет `-Dblib.server.version=1.21.10` (штатный обход самой библиотеки); вместе с BLib начинают работать BCases, BMenu, VirtualEntityApi |
| 19 young-GC за ~50 с, средняя пауза 41 мс, каждые ~2.6 с, аллокация 250 МБ/с | `GC_MODE=zgc` по умолчанию — паузы < 1 мс вместо 41 мс. Откат: `GC_MODE=g1` |
| CPU (system) 42–55%, I/O-стопы | `sync-chunk-writes=false` в `server.properties` (рекомендация Paper) |
| 35.5% медленных тиков в обфусцированных `oII.mloTI/mloOO` | имя плагина ищет `lagdoctor.sh` (по всем jar, включая вложенные библиотеки) |

Не трогает: дистанции, энтити-активацию, автосейв (они уже настроены),
плагины, миры, ресурспак.

## Установка

```bash
curl -fsSL -o /tmp/lagfix.zip https://raw.githubusercontent.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/<SHA>/elytrix-lagfix-v1.zip
unzip -oq /tmp/lagfix.zip -d /tmp/lagfix
bash /tmp/lagfix/install.sh /root/RW_GRIEF
```

Опции:

```bash
DISTANCE_TUNING=1 bash install.sh /root/RW_GRIEF   # view-distance<=8, simulation-distance<=6
NO_ZGC=1 bash install.sh /root/RW_GRIEF            # не трогать сборщик мусора
```

## После установки

1. Перезапустить сервер целиком (не `/reload`).
2. В логе проверить: `Server version 1.21.10 is set via property blib.server.version`
   и отсутствие `ExceptionInInitializerError` у BLib.
3. Запустить `bash lagdoctor.sh` из каталога сервера и прислать `lag-report.txt`.

## Как понять, что стало лучше

До: MSPT медиана 15.5, p95 29.6, max 155–448 мс, GC-паузы 41 мс каждые 2.6 с.
После ZGC в `logs/gc.log` не должно быть `Pause Young` с десятками миллисекунд,
а в spark `flat` — уйти строки `SafepointSynchronize::block` и
`G1CollectedHeap::attempt_allocation_slow`.

Остаток — это работа плагинов в главном потоке (50% времени медленных тиков).
Её убирает только правка конкретного плагина, который находит `lagdoctor.sh`.

## Откат

```bash
cd /root/RW_GRIEF
ls *.bak-lagfix-*
mv start.sh.bak-lagfix-<дата> start.sh
mv server.properties.bak-lagfix-<дата> server.properties
```
