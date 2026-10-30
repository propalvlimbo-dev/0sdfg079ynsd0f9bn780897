# Elytrix — Leaf 1.21.11 + оптимизированные конфиги + фикс плагина

Один пакет: ядро, конфиги, лаунчер и починенный `ElytrixFreakModel`.

## Одна команда

Сначала в консоли сервера: **`stop`** (установщик не ставит файлы на работающий
сервер и сам скажет об этом, если забыть).

Потом по SSH:

```bash
cd /root/RW_GRIEF && \
curl -fsSL -o /tmp/elytrix-leaf.zip https://raw.githubusercontent.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/1d19814da543b0b24c4932275c03915364505a22/elytrix-leaf-1.21.11.zip && \
rm -rf /tmp/elytrix-leaf && unzip -oq /tmp/elytrix-leaf.zip -d /tmp/elytrix-leaf && \
bash /tmp/elytrix-leaf/install.sh /root/RW_GRIEF
```

Потом:

```bash
cd /root/RW_GRIEF && bash start.sh
```

## Что именно ставится

| Файл | Что с ним | Почему |
| --- | --- | --- |
| `server.jar` | Leaf `1.21.11-179` (SHA-256 сверяется) | DivineMC убираем |
| `start.sh` | новый лаунчер | см. ниже |
| `bukkit.yml` | `autosave: 0`, `chunk-gc: 600` | убрать лишние автосейвы и частый обход чанков |
| `spigot.yml` | `restart-on-crash: false` | перезапуском занимается `start.sh`, иначе двойной запуск |
| `pufferfish.yml` | `tps-catchup: false` | «пила»: после лага сервер догоняет тики пачкой и лагает снова |
| `config/paper-global.yml` | `player-auto-save`: 12000 тиков, 2/тик | сейвы игроков реже и мягче |
| `config/leaf-global.yml` | `async-pathfinding.reject-policy: WAIT_FOR_COMPLETION`, `async-playerdata-save: true`, `OptimizeNonFlushPacketSending: true` | при переполнении очереди поиск пути больше не считается в главном потоке |
| `config/paper-world-defaults.yml` | без изменений | уже настроен нормально |
| `config/gale-*.yml` | без изменений | то же |
| `plugins/LagFixer/modules/WorldCleaner.yml` | `interval: 1080` (было 420) | обход всех сущностей 3 миров каждые 7 минут → 18 минут |
| `plugins/ElytrixFreakModel.jar` | v21 | `/аксессуары` больше не может выключить весь плагин |
| `versions/`, `divinemc*.yml`, `purpur.yml` | уводятся в бэкап | остатки DivineMC; `versions/` иначе может подсунуть старое ядро |

Не трогается: миры, `players/`, данные плагинов, `server.properties`, `eula.txt`,
ресурспак, остальные 85 плагинов.

## Что в новом `start.sh`

1. **Java 21+ ищется сам** (или `JAVA_BIN=/путь/к/java`), версия проверяется.
2. **Heap считается от машины**: 60% RAM, но не меньше 3 ГБ и не больше 12 ГБ.
   Было жёстко `-Xms10G -Xmx10G` — если на VDS 12–16 ГБ, это упирается в память
   машины. Переопределяется: `HEAP_MB=10G bash start.sh`.
3. **`-XX:MaxGCPauseMillis=200` вместо 100.** С 100 мс G1 обязан останавливать
   сервер не дольше 100 мс, поэтому он делает это часто и мельче — а на 10 ГБ
   heap всё равно упирается в потолок. Именно это даёт «ровный MSPT, потом
   резко ~100». Остальные флаги — Aikar.
4. **`-Xlog:gc*` в `logs/gc.log`** (5 файлов × 20 МБ). Раньше GC-пауз не было
   видно вообще: spark их не показывает, а лога не было. Через сутки в этом файле
   будет видно, есть ли паузы 100 мс (`grep 'Pause' logs/gc.log`) — и тогда
   решение принимается по данным, а не по догадке.
5. **Автоперезапуск после падения** (пауза 5 с, после 5 падений подряд — 60 с),
   но **не** после штатного `stop` (код 0) — сервер не будет оживать сам.
6. **Проверка модуля `jdk.incubator.vector`**: если сборка Java без него, сервер
   не падает с `Module ... not found`, флаг просто не добавляется.

Необязательно: `GC_MODE=zgc bash start.sh` — ZGC вместо G1 (паузы <1 мс, но
+10–15% CPU). Включать, только если в `gc.log` видно, что фризы — это GC, и
процессор не в потолке.

## Как понять, что стало лучше

Через 6–24 часа работы:

```bash
# максимальные паузы GC (ищем строки Pause с временем > 50 мс)
grep -E 'Pause (Young|Mixed|Full)' logs/gc.log | awk -F'ms' '{print $1}' | tail -3

# сколько раз GC останавливал сервер дольше 100 мс
grep -E 'Pause' logs/gc.log | grep -cE '[0-9]{3}\.[0-9]+ms' || true
```

В игре: `spark health`, `spark tps`, `spark tickmonitor --threshold-tick 40`.

Если спайки остались — запустить сборщик, который смотрит именно то, чего spark
не видит (троттлинг CPU контейнера, steal time, диск, cron):

```bash
curl -fsSL -o /tmp/elytrix-lag-diag.zip https://raw.githubusercontent.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/5928b03c0c5f19aa2bb480adf5ae862be06d1546/elytrix-lag-diag.zip && \
rm -rf /tmp/elytrix-lag-diag && unzip -oq /tmp/elytrix-lag-diag.zip -d /tmp/elytrix-lag-diag && \
bash /tmp/elytrix-lag-diag/collect.sh 90
```

## Откат

Всё, что заменялось, лежит в `/root/elytrix-backup-<дата>/` вместе с `MANIFEST`.
Откат одной командой (сервер должен быть остановлен):

```bash
bash /root/elytrix-backup-*/rollback.sh /root/RW_GRIEF
```

Скрипт вернёт старые файлы, удалит добавленные и вернёт убранные остатки
DivineMC (включая `versions/`). Миры и данные игроков не затрагивались ни
установкой, ни откатом.

## Честно о «100% без фризов»

Ни один конфиг не даёт гарантии: причина спайка может быть в троттлинге CPU
контейнера, steal time гипервизора, бэкапе на том же диске или в конкретном
плагине. Что делает этот пакет — убирает достоверно известные причины
(`MaxGCPauseMillis=100`, `tps-catchup`, чистка каждые 7 минут, лишние автосейвы,
поиск пути в главном потоке) и **включает измерение** GC-пауз, чтобы следующая
правка была по факту. Если после этого спайки останутся — `collect.sh` покажет,
что это не GC.
