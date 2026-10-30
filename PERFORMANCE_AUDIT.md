# Аудит производительности Elytrix — фиксация подозрений

Дата: 2026-10-31. Всё, что ниже, — **зафиксированные подозрения и факты**, а не
подтверждённый диагноз. Цель документа: не потерять их до момента, когда будем
собирать единую команду «ядро `server.jar` + оптимизированные конфиги + фикс
плагина».

## 0. Что известно точно (на момент записи)

- **Живое ядро: DivineMC `1.21.11-30-e6d50f0`** (`divinemc-1.21.11.jar`,
  `divinemc-api-1.21.11-R0.1-SNAPSHOT.jar`) — видно по стеку исключения
  `/аксессуары`. Ранее в проекте проверялись Pufferfish 1.21.10, Leaf 1.21.11 и
  DivineMC; **сейчас стоит DivineMC**, а не Leaf.
- `ElytrixFreakModel` на момент ошибки — **v3.2.10, disabled**:
  `PluginCommand.execute` → `Cannot execute command 'аксессуары' ... plugin is
  disabled`. То есть плагин не поднялся при старте, и вместе с меню умерли
  крылья, нимб, кагуне и повязка.
- Замеры spark (из истории проекта): `D9W5dkazXo` — 28 игроков, ~23,23 MSPT;
  `AVud5diK9b` — 35 игроков, ~26,34 MSPT, **max 423,92**. То есть одиночные
  спайки в сотни миллисекунд существуют давно и не зависят от онлайна.
- Симптом пользователя: MSPT ровный, потом резко до ~100, «сервер подлагивает»,
  **spark не показывает причину**.

## 1. Что у меня есть и чего нет

Есть (в git-снимке репозитория):

| Файл | Что даёт |
| --- | --- |
| `start.sh` | флаги JVM целиком — главная находка |
| `config/leaf-global.yml`, `config/gale-global.yml`, `config/gale-world-defaults.yml` | настройки Leaf/Gale-семейства |
| `config/paper-global.yml`, `config/paper-world-defaults.yml` | Paper-настройки |
| `purpur.yml`, `pufferfish.yml`, `bukkit.yml`, `spigot.yml` | остальные конфиги ядра |
| `plugins/LagFixer/modules/*.yml` | автоочистка, лимитеры, LagShield |
| `plugins/*/config.yml` | 86 плагинов |

Нет: `server.jar` (живого DivineMC), `logs/`, `spark`-выгрузок, `server.properties`
(в снимке отсутствует), данных о CPU/RAM VDS. Всё это надо получить командой
`tools/lag-diagnostics/collect.sh`.

## 2. Почему spark «ничего не пишет»

Сэмплер spark смотрит стек **главного потока сервера**. Он не видит:

1. **Паузы сборщика мусора** — главный поток стоит на safepoint, сэмплировать
   нечего.
2. **Троттлинг CPU по квоте контейнера (VDS)** — ядро морозит все потоки JVM на
   десятки-сотни миллисекунд, это не «работа кода».
3. **Steal time гипервизора** — соседняя виртуалка съела CPU.
4. **Дисковые затыки** (бэкап, `mysqldump`, rsync на том же диске) — поток ждёт
   в `read()`, такие кадры схлопываются в «I/O».

Плюс методическая ошибка: обычный `spark profiler` пишет **все** тики, и один
плохой тик тонет в сотнях нормальных. Для спайков нужен
`spark profiler start --only-ticks-over <ms>` (проверено по документации spark).

## 3. Подозрения по убыванию вероятности

### 3.1 GC: `-XX:MaxGCPauseMillis=100` в `start.sh`

```
-Xms10G -Xmx10G -XX:+UseG1GC -XX:MaxGCPauseMillis=100 ...
-XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 -XX:SurvivorRatio=32
-XX:MaxTenuringThreshold=1 ... -XX:+AlwaysPreTouch
```

Флаги — Aikar's, но **цель паузы занижена со 200 до 100 мс**. G1 вправе
останавливать сервер до 100 мс; при heap 10 ГБ mixed-GC регулярно упирается в
этот потолок. Симптом «ровно 100» совпадает с цифрой в конфиге.

- GC-лога нет (`-Xlog:gc*` не включён), поэтому спайки не в чем увидеть.
- Проверка: `collect.sh` (jstat + gc.log) либо `spark gc`.
- Направление лечения: включить GC-лог, посмотреть паузы; при подтверждении —
  либо меньше heap, либо ZGC (`-XX:+UseZGC -XX:+ZGenerational`, Java 21+ есть).

### 3.2 Троттлинг CPU на VDS (невидим для spark)

Проверяется только из ОС: `cpu.stat` (`nr_throttled`, `throttled_usec`),
`cpu.max` (квота), `st` в `vmstat`. Скрипт `collect.sh` снимает два замера и
считает дельту. Если `nr_throttled` растёт — все спайки оттуда, и никакой
профайлер их не покажет.

### 3.3 LagFixer: `WorldCleaner` каждые 420 секунд

`plugins/LagFixer/modules/WorldCleaner.yml`: `interval: 420` (7 минут),
`worlds: world, world_nether, world_the_end`, включены items/creatures/projectiles.
Это обход всех сущностей трёх миров в одном тике.

- Проверка: спайки идут строго каждые 7 минут? `spark tickmonitor` покажет.
- Лечение: увеличить интервал, разнести миры, отключить чистку предметов там,
  где она не нужна.

### 3.4 Три независимых автосейва

| Где | Значение | Период |
| --- | --- | --- |
| `paper-world-defaults.yml` `chunks.auto-save-interval` | 18000 | 15 мин |
| `paper-world-defaults.yml` `chunks.max-auto-save-chunks-per-tick` | 6 | — |
| `paper-global.yml` `player-auto-save.rate` | 6000 | 5 мин |
| `bukkit.yml` `chunk-gc.period-in-ticks` | 400 | 20 с |
| `bukkit.yml` `ticks-per.autosave` | 18000 | 15 мин |

Совпадающие периоды дают «дёргания» каждые 5/15 минут; при `flush-regions-on-save:
false` основная запись идёт пачкой.

### 3.5 `pufferfish.yml: tps-catchup: true`

Если DivineMC читает `pufferfish.yml`, после любого лага сервер догоняет
пропущенные тики пачкой → лагает снова → пила. Проверить по логу старта, какие
конфиги ядро реально читает (в DivineMC набор может отличаться от Leaf).

### 3.6 `leaf-global.yml` — возможно, не применяется вообще

Сейчас ядро DivineMC, а не Leaf. Файлы `config/leaf-global.yml`,
`config/gale-global.yml`, `purpur.yml` могут быть мёртвым грузом от прошлых
экспериментов. Если так, то:

- `async-pathfinding` с `reject-policy: CALLER_RUNS` (при переполнении очередь
  считает **главный** поток) — не работает и не мешает;
- но и все «оптимизации Leaf», на которые ссылались раньше, тоже не работают.

**Это отдельный пункт для будущей команды: выбрать ядро и привести конфиги в
соответствие ему, а не держать три набора одновременно.**

### 3.7 Наш собственный риг аксессуаров (v20)

В v20 `tickWornAngelRigs` пропатчен с `% 4` на `% 1`: риг крыльев/нимба/кагуне
обновляется 20 раз в секунду вместо 5. Это **постоянная** нагрузка (не спайк),
но если микролаги начались сразу после v20 — стоит проверить откатом.

### 3.8 Диск, бэкапы, внешняя MySQL

`region-format.io-thread-count: 6`, `compress-level: 6`, `io-flush-delay: -1`.
Любой параллельный `tar/rsync/mysqldump` на том же диске даёт ровно такие
спайки. `collect.sh` смотрит cron, systemd-таймеры и живые процессы бэкапа.

## 4. Как это проверить (уже готово)

```bash
cd /root/RW_GRIEF && \
curl -fsSL -o /tmp/elytrix-lag-diag.zip https://raw.githubusercontent.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/5928b03c0c5f19aa2bb480adf5ae862be06d1546/elytrix-lag-diag.zip && \
rm -rf /tmp/elytrix-lag-diag && unzip -oq /tmp/elytrix-lag-diag.zip -d /tmp/elytrix-lag-diag && \
bash /tmp/elytrix-lag-diag/collect.sh 90
```

В консоли сервера — только для спайков:

```
spark tickmonitor --threshold-tick 40
spark profiler start --only-ticks-over 60 --timeout 300
spark gc
```

GC-лог (добавить в `start.sh`, один раз):
`-Xlog:gc*:file=/root/RW_GRIEF/logs/gc.log:time,uptime,level,tags:filecount=5,filesize=20M`

## 5. План будущей команды «ядро + конфиги + фикс плагина»

Пока **не собрана** — здесь зафиксирован состав, чтобы не потерять.

1. Бэкап: `plugins/ElytrixFreakModel.jar`, `start.sh`, `server.jar`, все
   `*.yml`-конфиги ядра в `/root/elytrix-backup-<дата>/`, плюс `world` не трогаем.
2. `server.jar` — выбранное ядро (DivineMC или Leaf — решить до сборки), с
   проверкой `sha256` и версии в логе после старта.
3. Конфиги — **только под это ядро**, без смеси Leaf/Gale/DivineMC; в
   `start.sh` — GC-лог и согласованные флаги heap.
4. Фикс плагина — `ElytrixFreakModel.jar` из свежей сборки (v21+), в котором
   `onEnable` не может упасть из-за кода аксессуаров.
5. Проверка после старта: `Done`, `/аксессуары` открывается, в логе нет
   `plugin is disabled`, `spark health` не красный.
6. Откат: одна команда копирования из бэкапа + `restart`.

## 6. Открытые вопросы (нужны данные)

- Какие конфиги DivineMC реально читает при старте (список в логе).
- Сколько RAM/CPU у VDS и есть ли `cpu.max` квота.
- Периодичность спайков: каждые 7 минут / 15 / хаотично.
- Полный лог включения `ElytrixFreakModel` (причина `plugin is disabled`).
