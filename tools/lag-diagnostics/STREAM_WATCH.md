# Точечный контроль сервера во время стрима / большого онлайна

Живое ядро: **DivineMC `1.21.11`** (`/root/RW_GRIEF`), JVM-флаги в `start.sh`
(G1, `-XX:MaxGCPauseMillis=100`, `MaxDirectMemorySize=1536M`,
`-Dio.netty.maxDirectMemory=0`), 86 плагинов, `LagFixer`, `ModelEngine 4.1.0`
+ `ElytrixFreakModel v3.21.0`.

Документ — это чек-лист «что смотреть и когда бить тревогу». Всё наблюдение
делается **только чтением**: не перезапускает, не убивает процессы, не трогает
порты `:8085` / `:20559` / `:24454`.

---

## 0. Запуск (30 секунд, ничего ставить не надо)

```bash
# живой дашборд, экран обновляется раз в 10 секунд:
curl -fsSL https://raw.githubusercontent.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/<COMMIT_SHA>/tools/lag-diagnostics/live_watch.sh -o /root/live_watch.sh && bash /root/live_watch.sh 10 /root/RW_GRIEF
```

`Ctrl+C` -> сводка за всё время наблюдения + CSV-таймлайн в
`/root/elytrix-watch-<дата>/watch.csv`.

Если нужен **разовый глубокий дамп** (GC, steal, cron, диски, сеть) — уже есть
`tools/lag-diagnostics/collect.sh` (90 секунд, пишет в `/root/lagdump-*`).

---

## 1. Двенадцать точек контроля

| # | Что | Где смотреть | Порог тревоги | Что делать |
|---|---|---|---|---|
| 1 | **TPS / MSPT** | консоль: `/tick query` | `MSPT > 40` дольше 30 сек | снять профиль (см. §2) |
| 2 | **Паузы GC** | дашборд `GC макс. пауза`, `logs/gc.log` | `> 100 мс` (это ровно `-XX:MaxGCPauseMillis=100` из `start.sh`) | поднять цель до `200` **или** снизить мусор — см. §3.1 |
| 3 | **Heap** | дашборд `heap / heap%` | `> 85 %` и не падает после GC | `jcmd <pid> GC.run`, искать утечку плагина |
| 4 | **Off-heap / Direct** | дашборд `off-heap~` (RSS − heap) | монотонный рост, `> 1500 MB` | это Netty/PacketEvents/Via — §3.2 |
| 5 | **CPU steal** | дашборд `steal %` | `> 5 %` — VDS душат соседи | писать хостеру, снизить view-distance |
| 6 | **Диск** | дашборд `ДИСК util`, `iowait %` | `iowait > 20 %` или `util > 60 %` | проверить `mysqldump`/бэкап/cron на том же диске |
| 7 | **Потоки / FD** | дашборд `потоки` и `fd` | потоки растут монотонно (+100 за стрим) | утечка пула/планировщика — §3.3 |
| 8 | **`Can't keep up`** | дашборд, `logs/latest.log` | `> 0` стабильно | тик не влезает — пункты 2, 5, 6, 10 |
| 9 | **Ошибки плагинов** | дашборд `ПОСЛЕДНИЕ ОШИБКИ` | любой повторяющийся `Exception` | копировать стек, чинить точечно |
| 10 | **Сущности (ModelEngine)** | консоль или LagFixer | см. §4 — аксессуары множат `ItemDisplay` | §4 |
| 11 | **Онлайн / соединения** | дашборд `соединений на :25565` | резкий рост при падении TPS | бот-подключения / reconnect-шторм |
| 12 | **Чанки** | `loaded chunks` в консоли Paper | растёт без остановки | утечка загрузки чанков (RTW, `/rtp`, FAWE) |

---

## 2. Если тик просел: как поймать причину

Обычный профиль бесполезен — один плохой тик тонет в сотнях нормальных.
Нужен профиль **только по плохим тикам**:

```
/spark profiler start --only-ticks-over 50
# подождать 2–3 минуты на пике онлайна
/spark profiler stop
```

Если Spark не стоит — он однофайловый (`spark.jar` в `plugins/`), ставится без
перезагрузки конфигов и не конфликтует с LagFixer.

Дальше по убыванию вероятности на **этом** сервере:

1. GC-пауза 100 мс (п. 2 таблицы) — Spark её не увидит.
2. Троттлинг/steal VDS — Spark её не увидит.
3. Диск (бэкап/`mysqldump`) — Spark её не увидит.
4. Массовая правка **FastAsyncWorldEdit** — увидит как `editSession`/`setBlock`.
5. **Аксессуары ModelEngine** — `ActiveModelImpl.tick` / `DisplayRendererImpl`.
6. **TAB** с тяжёлыми плейсхолдерами при большом онлайне — `TAB` в профиле.

---

## 3. Три типовых лечения

### 3.1 Фриз «ровно 100 мс» — цель GC

В `start.sh` стоит `-XX:MaxGCPauseMillis=100` (вместо классических 200). G1
имеет право останавливать сервер на 100 мс, и при heap 4.6–8 ГБ регулярно в
этот потолок упирается. Симптом «сервер фризит ровно на 100 мс» совпадает
с цифрой в конфиге.

Правка (`start.sh`, строка с `MaxGCPauseMillis`):

```
-XX:MaxGCPauseMillis=200
```

Плюс (уже есть в `start.sh`, не трогать): `-XX:+ExplicitGCInvokesConcurrent`,
`-XX:G1PeriodicGCInterval=30000`, `-XX:MaxDirectMemorySize=1536M`,
`-Dio.netty.maxDirectMemory=0`.

### 3.2 Off-heap / DirectMemory растёт

`-Dio.netty.maxDirectMemory=0` перевёл Netty на JDK Cleaner под общий лимит
`MaxDirectMemorySize=1536M` — это правильно, но буферы освобождаются только по
GC. Если `off-heap~` в дашборде ползёт вверх и не откатывается:

```
jcmd <pid> GC.run          # принудительный concurrent GC
jcmd <pid> VM.native_memory summary   # только если JVM запущен с -XX:NativeMemoryTracking
```

Если после `GC.run` не отпустило — виновен конкретный плагин-пакетчик
(ProtocolLib / ViaVersion / PacketEvents / KnockbackSync), лечится рестартом
в окне низкого онлайна, а не на стриме.

### 3.3 Потоки растут

```
ls /proc/<pid>/task | wc -l
jcmd <pid> Thread.print | grep -c '^"'
jcmd <pid> Thread.print | grep '^"' | sed 's/[0-9]\+//g' | sort | uniq -c | sort -rn | head
```

Топ имён покажет, чей пул течёт.

---

## 4. Аксессуары `ElytrixFreakModel` при большом онлайне

Это **главная новая нагрузка**, которой раньше не было: каждая надетые шапка
или пет — это отдельные `ItemDisplay` на игроке.

| Аксессуар | Костей (display-сущностей) на игрока |
|---|---|
| `Дождевое облако` (`elytrix_lightning_hat`) | **13** |
| `Круг Сатаны` (`elytrix_satan_circle`) | **7** |
| `Щупальца Канэки` (`elytrix_kaneki_tentacles`) | **55** |
| `Сколопендра Гуля` (`elytrix_centipede`) | ~60 |

То есть **60 игроков в кагуне — это 3300 сущностей**. Держите в голове:

- В `plugins/LagFixer/modules/EntityLimiter.yml` стоит `ignore_models: true` —
  **не выключайте**: иначе Limiter начнёт убивать кости аксессуаров, и модели
  начнут мигать/пропадать.
- `VIEW_RANGE = 48` в `AccessoryController` — радиус видимости аксессуаров.
  Если MSPT просел именно на `ActiveModelImpl.tick`, это первое, что урезают.
- Все аксессуары скрыты от 1-го лица через `minecraft:constant` тинт
  `-196867` в шейдерах RP — клиентская нагрузка минимальна, серверная считается.

---

## 5. Что НЕ делать на стриме

- Не запускать `collect.sh` и `live_watch.sh` одновременно на одном `DUMPDIR`
  (перезапишут друг друга — задайте разный `DUMPDIR`).
- Не перезапускать сервер «чтобы полегчало» без снятия профиля — потеряете
  улики.
- Не менять `config/paper-global.yml`, `plugins/ModelEngine/config.yml`,
  `owned_accessories.yml` и базы — они не входят в деплой-архивы намеренно.
- Не трогать порты `:8085` (раздача RP), `:20559`, `:24454`.

---

## 6. Экспресс-проверка «одной командой» (без установки)

```bash
P=$(pgrep -f 'java .*server.jar' | head -1); echo "PID=$P"; \
awk '{print "load: "$1" "$2" "$3}' /proc/loadavg; \
grep -c "Can't keep up" /root/RW_GRIEF/logs/latest.log; \
tail -n 2000 /root/RW_GRIEF/logs/gc.log | grep -oE '[0-9]+\.[0-9]+ms$' | sort -g | tail -3; \
awk '/MemAvailable/{printf "RAM free: %d MB\n",$2/1024}' /proc/meminfo; \
[ -n "$P" ] && awk '{printf "RSS: %d MB\n",$2*4096/1048576}' /proc/$P/statm; \
[ -n "$P" ] && awk '/^Threads:/{print "threads: "$2}' /proc/$P/status
```

Показывает: load, число «Can't keep up» за весь лог, три худшие паузы GC,
свободную RAM, RSS и потоки Java. Достаточно, чтобы за 5 секунд понять,
**где** горит.
