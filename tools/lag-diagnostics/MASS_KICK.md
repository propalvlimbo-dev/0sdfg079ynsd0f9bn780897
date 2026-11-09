# Массовый кик: «вылетают все одновременно»

Симптом: без фризов и без просадки TPS **всех игроков выкидывает в одну секунду**.

## 0. Florium

В снимке сервера (`plugins/`) плагина **Florium нет** — установлены `GrimAC`,
`LPX`, `ProtocolLib`, `ViaVersion` + `ViaBackwards`, `KnockbackSync`,
`AntiDisconnectSpam`. У GrimAC все `punish-commands` закомментированы, то есть
**Grim никого не кикает**. Значит основной подозреваемый — **LPX** (плюс
Paper `packet-limiter` как второй).

---

## 1. Диагностика за 20 секунд

```bash
bash /root/kick_why.sh /root/RW_GRIEF/logs/latest.log
```

Скрипт печатает:
1. **топ-5 минут** по числу `lost connection` — точная минута массового кика;
2. **причины отключений** по частоте;
3. кто кикал: LPX / Paper packet-limiter / Netty-ProtocolLib / таймауты;
4. **контекст за эту минуту** — что было прямо перед киком;
5. авто-вывод с готовым лечением.

---

## 2. Причина №1 — LPX `kick-on-exception: true` ⭐ самая вероятная

В `plugins/LPX/config.yml` было:

```yaml
options:
  # Whether LPX should kick players when an exception in their handlers occurs
  kick-on-exception: true
```

LPX кикает игрока **при любом исключении внутри своего обработчика пакетов**.
Стоит одному типу пакета (общему для всех — например `CLIENT_TICK_END`,
оконный/предметный пакет от кейсов, меню или TAB) вызвать NPE — **вылетают все
сразу**, с сообщением `You are sending suspicious packets.`

**Исправлено в репозитории:**

```yaml
  kick-on-exception: false      # исключение только в лог, игроки НЕ вылетают
```

Плюс ослаблены слишком резкие проверки (один флаг = мгновенный кик):

| Проверка | Было | Стало |
|---|---|---|
| `checks.netty.a` | `max-vl: 3` | `max-vl: 8` |
| `checks.netty.b` | `max-vl: 1` | `max-vl: 5` |

`netty.b` — это глубина NBT и число предметов в пакете. С учётом
`ViaVersion`/`ViaBackwards` (перевод пакетов 1.21.11 ↔ старые версии) и
кастомных предметов (`ElytrixItems`, `BCases`) один ложный флаг раньше
мгновенно кикал.

---

## 3. Причина №2 — Paper `packet-limiter`

`config/paper-global.yml`:

```yaml
packet-limiter:
  all-packets:
    action: KICK
    interval: 7.0
    max-packet-rate: 500.0     # ~71 пакет/сек
```

При всплеске (спавн 3D-аксессуаров `ModelEngine`, обновление TAB/скорборда,
отправка чанков) часть игроков пробивает лимит и получает кик
`Sent too many packets too quickly`.

> ⚠️ `config/paper-global.yml` **НЕ входит** в деплой-архивы — правится только
> на VDS, точечно:

```bash
sed -i 's/^    max-packet-rate: 500.0/    max-packet-rate: 1500.0/' /root/RW_GRIEF/config/paper-global.yml
grep -A3 '^packet-limiter:' /root/RW_GRIEF/config/paper-global.yml
```

Дополнительно в `plugins/AntiDisconnectSpam/config.json` добавлены причины
Paper (`Sent too many packets`, `disconnect.exceeded_packet_rate`, …), чтобы
даже при срабатывании лимитера игрок не вылетал.

---

## 4. Причина №3 — Netty / DirectMemory

Если в логе `Internal Exception: io.netty…` или `OutOfDirectMemoryError` —
это не LPX. Проверить:

```bash
bash /root/live_watch.sh 10 /root/RW_GRIEF     # смотреть строку off-heap~
```

Лимит в `start.sh`: `-XX:MaxDirectMemorySize=1536M` +
`-Dio.netty.maxDirectMemory=0`. Если `off-heap~` подползает к 1500 MB и не
откатывается — виновен плагин-пакетчик (ProtocolLib / Via / PacketEvents),
лечится рестартом в окне низкого онлайна.

---

## 5. Причина №4 — таймауты

`Timed out` у всех сразу = симптом, а не причина: сервер перестал отвечать на
keep-alive. Смотреть пункты 2–4 и `live_watch.sh` (GC/steal/диск).

---

## 6. Что уже безопасно

- `bukkit.yml`: `connection-throttle: -1` — шторм реконнектов после массового
  кика **не** добивает повторными отказами.
- `GrimAC`: все `punish-commands` закомментированы — Grim никого не кикает.

---

## 7. Как применить прямо сейчас

```bash
# 1. конфиги (LPX + AntiDisconnectSpam) — безопасно, без рестарта конфигов ядра
curl -fsSL https://raw.githubusercontent.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/<SHA>/plugins/LPX/config.yml -o /root/RW_GRIEF/plugins/LPX/config.yml
curl -fsSL https://raw.githubusercontent.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/<SHA>/plugins/AntiDisconnectSpam/config.json -o /root/RW_GRIEF/plugins/AntiDisconnectSpam/config.json

# 2. поднять лимит пакетов Paper (НЕ через архив!)
sed -i 's/^    max-packet-rate: 500.0/    max-packet-rate: 1500.0/' /root/RW_GRIEF/config/paper-global.yml

# 3. перечитать конфиги без рестарта
#    в консоли сервера:
lpk reload        # или /lpx reload
```

Если `/lpx reload` нет — применится после рестарта, но `kick-on-exception`
читается на старте, так что в окне низкого онлайна всё же перезапустите.
