# Установка v22 на VDS

**Одной командой лучше ставить ядро**: пакет `elytrix-leaf-1.21.11.zip` уже содержит
этот jar (`tools/core-install/`). Если менять ядро пока не нужно — ниже только плагин.

## Только плагин (ресурспак не менялся)

SHA-1 пака остаётся `7173523183d1e1f76d011702a350b44fadcd99bb`, поэтому ресурспак
копировать не обязательно.

```bash
cd /root/RW_GRIEF && set -e && \
curl -fsSL -o /tmp/elytrix-v22.zip https://raw.githubusercontent.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/1d19814da543b0b24c4932275c03915364505a22/elytrix-tentacles-v22.zip && \
B=/root/elytrix-backup-$(date +%Y%m%d-%H%M%S) && mkdir -p "$B" && \
cp -a plugins/ElytrixFreakModel.jar "$B/" && \
unzip -oq /tmp/elytrix-v22.zip plugins/ElytrixFreakModel.jar -d /root/RW_GRIEF && \
sha256sum plugins/ElytrixFreakModel.jar
```

Ожидаемый SHA-256: `21fb71176403dd6755fbec463de0d0aa08e88761d2f5b1e41c1b3abffa9fec50`
(в jar теперь `version: 3.3.0`). После — `restart`.

## Что в v22

### 1. Повязка Канэки теперь реально рисуется

Раньше плагин добавлял модель повязки **вторым** `ActiveModel` на
`ModeledEntity` игрока и не выполнял ключевой шаг, который делает риг крыльев/нимба:
`PivotOverride.addPassenger(pivotId)` — привязку модели к пивоту игрока. Плюс
`syncPlayerWornAngelRig` при пустом риге каждый тик **уничтожал** этот
`ModeledEntity`, то есть нашу модель стирало 20 раз в секунду.

Теперь повязка идёт через **слот нимба** — единственный путь в этом плагине,
который умеет цеплять модель к голове игрока и корректно её убирать:

- `halo(player)` возвращает спеку нимба при `head = halo` и спеку повязки при
  `head = eyepatch`;
- blueprint `elytrix_kaneki_eyepatch` — из того же пакета, размеры уже на лице;
- нимб и повязка взаимно исключаются (это один слот головы), кагуне и крылья —
  отдельный слот спины, всё сочетается;
- из ASM-патча убран пятый хук (`tickEyepatch`), осталось четыре проверенных.

### 2. Меню

- **Кнопки «Назад» больше нет.**
- **«Снять всё» — в самом низу по центру** (слот 49).
- Крылья / нимб / щупальца / повязка — клик надевает, повторный клик снимает;
  на надетом предмете висит строка `§a● Сейчас надето`.

### 3. Доступ для доната `media`

При включении плагин один раз выполняет
`lp group media permission set elytrixaccessories.use true`.
Проверить: `/lp group media info` — должен быть `elytrixaccessories.use = true`.

## Откат

```bash
cp -f /root/elytrix-backup-*/ElytrixFreakModel.jar /root/RW_GRIEF/plugins/ && restart
```
