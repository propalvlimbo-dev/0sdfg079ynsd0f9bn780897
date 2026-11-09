# Обновление сборки Elytrix (1.21.10 Leaf) — Полный отчёт

Скачать полную готовую сборку одним архивом (`plugins/` + `rp/` + оптимизированные конфиги ядра):
👉 **[Скачать архив сборки (ZIP)](https://github.com/propalvlimbo-dev/0sdfg079ynsd0f9bn780897/archive/refs/heads/arena/4c55e5a6-0sdfg079ynsd0f9bn780897.zip)**

---

## Выполненные задачи

### 1. Исправление анимации кейсов (`NCases-1.jar` + `NCases/config.yml`)
- **Без стягивания к центру**: переписана фаза вращения `RotatingCircleAnimation.runAsyncWheel()` — сначала плавный радиальный вылет на полный радиус (`12` тиков), затем вращение с математической компенсацией клиентской 3-тиковой хордовой интерполяции Minecraft (`baseRadius / cos(stepDeg * 1.28)`), благодаря чему предметы держат ровный круг и не сужаются к центру.
- **Удалена звезда**: полностью убран `NETHER_STAR` из анимации и байткода.
- **Увеличена длительность прокрутки**: длительность вращения увеличена до `148` тиков (~7.4 сек вращения + вылет и финальный показ приза в верхней точке = ~9.6 сек полного цикла).

### 2. Скорборд (`plugins/TAB/config.yml`)
- Удалён плейсхолдер `%expirytime%` из строки `Ранг: %luckperms_prefix%`.

### 3. Новый порядок и цены доната (`ANGEL` предпоследний, `D.HELPER` — `499р`)
Выстроена сбалансированная лестница платных привилегий во всех системах (`LuckPerms` H2 БД, `TAB`, `/donate` + текстура `content_56.png`, голограммы `don1.yml` / `don2.yml`, `ElytrixGranter`):
1. `DRAGON` (`ꔨ`, weight `8`) — **39 руб.**
2. `BULL` (`ꔲ`, weight `10`) — **69 руб.**
3. `RABBIT` (`ꕒ`, weight `14`) — **109 руб.**
4. `HYDRA` (`ꕀ`, weight `15`) — **159 руб.**
5. `COBRA` (`ꕈ`, weight `17`) — **219 руб.**
6. `GOD` (`ꕁ`, weight `22`) — **289 руб.**
7. `PEGAS` (`ꕉ`, weight `24`) — **379 руб.**
8. **`D.HELPER`** (`ꕠ`, weight `25`) — **499 руб.**
9. **`ANGEL`** (`ꕓ`, weight `26`, **предпоследний**) — **899 руб.**
10. **`D.ADMIN`** (`ꕡ`, weight `27`, **последний**) — **3000 руб.**

### 4. Очистка наборов и кастомное RP-меню предпросмотра китов (`/kits`)
- Удалены наборы `PVE`, `FARM`, `MAGISTER`, `OVERLORD`, `AVENGER`, `TITAN`, `HERO` из `nKits`, `Essentials`, `LuckPerms` и `/kits` (также починен формат `vampire.yml` под `nKits` 1.21.10).
- Перерисована текстура меню `/kits` (`content_39.png`, глиф `ꌹ`) под симметричную сетку из **18** оставшихся наборов (два крыла 3×3 с розовым разделителем `#F8BEFB`).
- Создана кастомная RP-текстура предпросмотра набора (`content_kit_preview.png`, глиф `ꍗ`) и сгенерированы **18** меню `DeluxeMenus/gui_menus/kits_preview/preview_<kit>.yml` (открываются по ПКМ в `/kits`): слева — стойка брони и слот второй руки (кастомный шар/тотем), справа — хранилище 7×5 со всеми предметами набора, снизу — RP-кнопки **«◄ НАЗАД»** и **«✚ ПОЛУЧИТЬ»**.

### 5. Легендарный кейс за 89 рублей
- Настроен **`ЛЕГЕНДАРНЫЙ КЕЙС — СУПЕР КЕЙС С ДОНАТОМ`** по цене **89 руб. за 1 шт.** (выпадают только топовые привилегии от `COBRA` до `D.ADMIN`).
- Обновлены `NCases/config.yml`, `NCases/admin.yml`, `DeluxeMenus/gui_menus/priv/cases.yml` (верхняя правая карточка со значком золотой короны в `content_55.png`), а также голограммы `don1.yml` и `don2.yml`.

### 6. Замена `Citizens` на `FancyNpcs 2.10.0`
- Полностью удалён устаревший `Citizens` и установлен пакетный **`FancyNpcs-2.10.0.jar`** (`1.21.10`, нулевая нагрузка на физику и тики сущностей).
- Все **26 NPC** перенесены в `plugins/FancyNpcs/npcs.yml` с сохранением команд клика, многострочных голограмм в `displayName`, экипировки в руках и восстановлением точных высот `Y` на поверхности `world_spawn` (в старом `Citizens` все NPC провалились в пустоту на `Y = -65` / `-4370`).

### 7. Глубокая оптимизация конфигов ядра Leaf 1.21.10 под 1000 онлайна и ультра-плавное PvP
Распакованы и оптимизированы все 9 конфигов ядра (`bukkit.yml`, `spigot.yml`, `pufferfish.yml`, `purpur.yml`, `config/paper-global.yml`, `config/paper-world-defaults.yml`, `config/gale-global.yml`, `config/gale-world-defaults.yml`, `config/leaf-global.yml`):
- **Плавность PvP**: `flush-location-while-knockback-player: true` (мгновенная отправка пакета откидывания без задержек), сохранены точные пакеты движения игроков (`reduce-entity-move-packets: false`, `reduce-entity-motion-packets: false`), `async-entity-tracker: false` и `OptimizeNonFlushPacketSending: false` (полная совместимость с `ProtocolLib`, `FancyNpcs` и виртуальными сущностями без рассинхрона хитбоксов), `optimize-explosions: true`, дальность трекинга игроков `72` блока.
- **Производительность на 1000 игроков**: `async-chunk-send: true`, `async-pathfinding: true` (4 потока), `async-mob-spawning: true`, `async-playerdata-save: true`, JDK 21 Virtual Threads для планировщика/чата/авторизации, `ALTERNATE_CURRENT` редстоун, `DAB` для дальних мобов, `Xoroshiro128PlusPlus` RNG, XXHash для биомов, `view-distance: 6` / `simulation-distance: 4`, `use-alternate-keepalive: true`.

### 8. Плагин обязательного ресурспака (`ElytrixRP.jar`)
- Написан и скомпилирован лёгкий плагин **`ElytrixRP.jar`** (`plugins/ElytrixRP/config.yml`).
- Достаточно вставить прямую ссылку на архив ресурспака (`rp/Elytrix-RP-1.21.zip`) в поле `url: ''` в `plugins/ElytrixRP/config.yml` и ввести `/elytrixrp reload` — плагин автоматически отправляет обязательный ресурспак при входе и кикает при отказе или сбое скачивания.

### 9. Кастомные 3D-шары `ANGEL` и `D.ADMIN` (`ElytrixItems` + RP + Киты)
- В ресурспак (`rp/Elytrix-RP-1.21.zip`) добавлены 3D-модели и 16-кадровые анимированные текстуры **`Шар Ангела`** (`CustomModelData: 5012`, `sphere/angel`) и **`Шар Д.Админа`** (`CustomModelData: 5013`, `sphere/dadmin`) во все 3 файла `player_head.json`.
- В `plugins/ElytrixItems/config.yml` добавлены `angel_ball` (`+3 Брони`, `+6 Здоровья`, `+2.5 Урона`, `+15% Скорости`, `SHIFT`: Сопротивление II на 8 сек) и `dadmin_ball` (`+4 Брони`, `+10 Здоровья`, `+3.5 Урона`, `+20% Скорости`, `SHIFT`: Сила III на 8 сек).
- Оба шара положены сразу в слот второй руки (`slot 40`) в наборах `nKits/Kits/angel.yml` и `nKits/Kits/dadmin.yml`.

### 10. Замена `AntiRelog` на `GreatCombat 1.9`
- Полностью удалены `AntiRelog` и `AntirelogScoreboard`.
- Установлен **`GreatCombat-1.9.jar`** (`locale: ru`, 30 сек режим боя, отключение `FLY/GOD/GM/VANISH/WALKSPEED`, убийство при выходе, кулдауны: гепл `5с`, чарка `10с`, пёрл `15с`, хорус `5с`, фейерверк `8с`) с боевым скорбордом через **`TAB`** и розовым BossBar/ActionBar в стиле `Elytrix`.

### 11. Удаление старого `/free` и переработка `ElytrixFree` с RP-меню и наградами ReallyWorld
- Удалено старое меню `DeluxeMenus/gui_menus/free.yml`.
- В `ElytrixFree.jar` обновлён загрузчик кастомных голов (`Skulls.class`) на современный API `PlayerProfile` Paper 1.21.10 (без ошибок рефлексии на Java 21) и установлен `api-version: "1.21"`.
- Отрисовано кастомное 54-слотовое RP-меню (`content_elytrix_free.png`, глиф `ꍘ`) с 10 наградами за наигранное время (`free1..free10`, сетка 5×2) в стиле ReallyWorld: риллики (`ꐃ`), игровая валюта, кейсы (`money`, `rilik`, `ditems`, `donate`, `vsoilinichigo`, `legendary`), трапки, дезориентации, кастомные шары и привилегии (`IMPERATOR`, `DRAGON`), а также промокоды на риллики и кейсы в `code.yml`.
