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
| `[STDOUT] [OlI] [websocket] disconnected (code=1002)` и поток `WebSocketConnectReadThread-11981182` | `lagdoctor.sh` ищет клиент Java-WebSocket: переподключение в цикле = новый поток и буферы на каждую попытку (11.9 млн за аптайм), отсюда 250 МБ/с аллокации и всплески MSPT |

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

1. Перезапустить сервер **целиком** — флаг `-Dblib.server.version` применяется только при старте JVM.
   `/plugman reload BLib` его не подхватит: в логе снова будет `UnsupportedVersionException`.
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

## Окно наблюдения 30 минут (spark30.sh)

Ссылка spark за 30 минут показывает среднюю картину: один всплеск на 0.6 с
растворяется в 30 минутах нормальной работы. Поэтому данные собираются в двух
видах, и оба — текстовые, в логе:

```
/spark tickmonitor --threshold-tick 100
/spark profiler start --timeout 1800 --only-ticks-over 100
```

Первый печатает в консоль и `latest.log` каждую строку `Tick #N lasted 214.6 ms`
и `Tick #N included GC lasting 41.2 ms` — с отметкой времени. Второй пишет
профиль только по медленным тикам, поэтому всплески не размываются.

Оба работают одновременно: у spark несколько обработчиков тика
(`TickHook.addCallback`), конфликта нет.

Когда окно закончилось:

```
bash spark30.sh /root/RW_GRIEF report 30
```

Разбор считает по минутам: сколько было переподключений websocket, сколько
медленных тиков и пауз GC, и сравнивает минуты «со штормом» и «без». Если
медленные тики сосредоточены в минутах со штормом — это доказательство со
стороны сервера.

Снимок «прямо сейчас» (10 секунд, без spark):

```
bash spark30.sh /root/RW_GRIEF
```

Смотрит в `/proc/<pid>/status`: переключения контекста в секунду, число потоков,
и рост TIME_WAIT-сокетов. Шторм переподключений виден по >20000
переключений/сек и растущим десятками TIME_WAIT.
