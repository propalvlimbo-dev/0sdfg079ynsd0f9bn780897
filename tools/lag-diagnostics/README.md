# Диагностика микролагов Elytrix

Проблема: MSPT ровный, но иногда резко прыгает до ~100, сервер подлагивает,
а spark «ничего не пишет».

## Почему spark молчит

Сэмплер spark смотрит стек **главного потока**. Он физически не видит:

1. **Паузы сборщика мусора.** Во время GC главный поток стоит на safepoint —
   сэмплировать нечего, в отчёте будет «пусто» или последний кадр.
2. **Троттлинг CPU по квоте контейнера (VDS).** Когда исчерпана квота, ядро
   замораживает все потоки JVM на 100–500 ms. Это не «работа кода», это
   отсутствие CPU — spark покажет провал, а не причину.
3. **Steal time гипервизора** — то же самое, но от соседней виртуалки.
4. **Дисковые затыки** (бэкап/rsync/mysqldump на том же диске): главный поток
   просто ждёт в `read()`, а такие кадры spark схлопывает в «I/O».

Плюс самая частая ошибка: обычный профиль пишет **все** тики, и один плохой
тик тонет в сотнях нормальных. Для спайков нужен
`--only-ticks-over` — тогда в отчёт попадают только медленные тики.

## Что запустить в консоли сервера

```
spark tickmonitor --threshold-tick 40
```
Показывает каждый тик длиннее 40 ms — так видно, **как часто** идут спайки
(раз в 7 минут? раз в 15? хаотично?). Это уже половина диагноза.

Когда спайки идут:
```
spark profiler start --only-ticks-over 60 --timeout 300
spark profiler stop
```
В отчёте будут **только** тики медленнее 60 ms.

```
spark gc
spark health --upload
```
`spark gc` — история пауз сборщика; `spark health` — сводка по CPU/памяти/диску.

## Что запустить в SSH

```bash
cd /root/RW_GRIEF && \
curl -fsSL -o /tmp/elytrix-lag-diag.zip https://raw.githubusercontent.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/5928b03c0c5f19aa2bb480adf5ae862be06d1546/elytrix-lag-diag.zip && \
rm -rf /tmp/elytrix-lag-diag && unzip -oq /tmp/elytrix-lag-diag.zip -d /tmp/elytrix-lag-diag && \
bash /tmp/elytrix-lag-diag/collect.sh 90
```

Скрипт только читает: ничего не перезапускает, не убивает процессы, не трогает
`:8085`, не пишет вне `/root/lagdump-*`. В конце печатает короткий отчёт —
его можно целиком скопировать в чат.

Что он собирает:

| Блок | Зачем |
| --- | --- |
| Java PID, cmdline, `VM.flags`, `GC.heap_info` | какие флаги реально применены, сколько живых объектов |
| `nproc`, память, своп, `dirty`, `writeback` | не упирается ли сервер в RAM/своп |
| `cpu.max`, `cpu.stat` (два замера) | **троттлинг квоты CPU** — главный невидимый виновник на VDS |
| `jstat -gcutil` (два замера) | сколько пауз GC и какая средняя пауза за окно |
| `Pause ... ms` из `gc.log` | топ-5 самых долгих пауз, если GC-лог включён |
| `vmstat` (`r`, `wa`, `st`), `iostat`, `df` | диск, очередь, steal time гипервизора |
| `crontab`, timers, процессы бэкапов | что параллельно грузит диск |
| `server.properties`, размеры миров, region-файлы | view/simulation-distance, размеры |
| `latest.log` | ядро и версия, `Can't keep up`, последние WARN/ERROR |

## Включить GC-лог (один раз, потом спайки видно сразу)

В `start.sh`, в строку флагов Java, добавить:

```
-Xlog:gc*:file=/root/RW_GRIEF/logs/gc.log:time,uptime,level,tags:filecount=5,filesize=20M
```

После перезапуска любой спайк виден строкой вида

```
[2026-10-31T12:00:00.123+0300][12345.678s][info][gc] GC(421) Pause Young (Normal) (G1 Evacuation Pause) 5120M->1024M(10240M) 87.456ms
```

Если длительность паузы ≈ длительности спайка MSPT — виноват GC, и дальше
лечится флагами (`-XX:MaxGCPauseMillis`, размер heap, переход на ZGC на Java 21+).

## Что подозрительно именно в текущих конфигах

1. **`start.sh`: `-XX:MaxGCPauseMillis=100`.** Это не «максимум 100 ms в среднем»,
   это разрешение G1 останавливать сервер до 100 ms. Ровно твоё «резко до 100».
   Aikar's flags ставят 200 (то есть разрешают ещё больше), поэтому если паузы
   реально мешают — это не «подкрутить», а либо меньше heap, либо ZGC.
2. **`plugins/LagFixer/modules/WorldCleaner.yml`: `interval: 420`.** Каждые
   **7 минут** плагин обходит все сущности трёх миров. На сервере с 1000+ мобов
   и предметов это и есть периодический спайк. Проверка: спайки идут ровно
   каждые 7 минут?
3. **Автосейвы:** `paper-world-defaults.yml` `auto-save-interval: 18000`
   (15 минут, `max-auto-save-chunks-per-tick: 6`), `bukkit.yml`
   `chunk-gc.period-in-ticks: 400` (20 секунд), `player-auto-save.rate: 6000`
   (5 минут). Три разных периода — три разных «дёргания».
4. **`pufferfish.yml`: `tps-catchup: true`.** Если текущее ядро этот файл читает —
   после каждого лага сервер догоняет упущенные тики пачкой и лагает снова
   (пила). Проверить в логе старта, читает ли ядро `pufferfish.yml`.
5. **`leaf-global.yml`: `async-pathfinding.reject-policy: CALLER_RUNS`.** Когда
   очередь (4096) переполнена, поиск пути считает **главный** поток — одиночный
   спайк на десятки миллисекунд.
6. **`paper-global.yml`: `packet-limiter`** с `max-packet-rate: 500` за 7 секунд и
   действием `KICK`. Это не MSPT, но при массовом PvP может ронять игроков.

## Полезные команды на будущее

```
spark tps                 # текущий TPS/MSPT
spark tickmonitor --threshold-tick 40
spark profiler start --only-ticks-over 60 --timeout 300
spark gc                  # история пауз GC
spark heapsummary         # что занимает память (без тяжёлого heapdump)
```
