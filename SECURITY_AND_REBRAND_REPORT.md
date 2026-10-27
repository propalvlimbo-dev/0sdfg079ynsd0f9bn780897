# Отчёт по очистке от хаков/ратников и полному ребрендингу **Elytrix 1.21**

## 1. Проверка на хаки и вредоносный код (Найдено и полностью обезврежено)

В исходной сборке была обнаружена **многоуровневая цепочка заражения (RAT / дроппер / бэкдор-аккаунты)**:

### А. Удалённые отдельные вредоносные JAR-файлы
1. **`plugins/bstats.jar`** — замаскированный под библиотеку метрик троян-загрузчик (`ru.bstats.MetricsLoader` + `ru.sollyantirek.bstatsloader.HookHandler`), который подгружал внешний бэкдор с `https://panel.bstats.co/downloads/bstats.jar`. **Полностью удалён.**
2. **`plugins/PlaceholderAPI/expansions/Expansion-christmasapi.jar`** и **`Expansion-utilities.jar`** — вредоносные PAPI-расширения (бэкдор `christmass1405` / `chexclassic`). **Полностью удалены.**

### Б. Вылеченные заражённые плагины (18 `.jar` файлов)
В **18 плагинов** злоумышленниками был вшит вредоносный код прямо в метод `onEnable()`:
- **Семейство №1 (`SystemMetrics` дроппер `panel.bstats.co`)** — скачивал и запускал троян при каждом старте сервера.
- **Семейство №2 (`org/apache/commons/lang3/MutableUtilities` + `AccessMake` + `TextChatComponent$EmbedObject`)** — **полноценный RAT (365 классов внутри каждого заражённого плагина)** с эксфильтрацией данных и управлением через Discord Webhook.

Все 18 плагинов вылечены на уровне байткода JVM (OpenJDK 21): удалены все вредоносные классы, вызовы в `onEnable()` нейтрализованы (`NOP`), константные пулы очищены и верифицированы:
- `AntiRelog.jar`, `AntirelogScoreboard.jar`, `IRandomTeleport.jar`, `LiteBans.jar`, `LuckPerms.jar`, `MyCommand.jar`, `MythicMobs-5.13.0.jar`, `NAuras.jar`, `NCases-1.jar`, `NClans-1.jar`, `PlayerPoints.jar`, `ProtocolLib.jar`, `ElytrixGrowGarden.jar` (`Really-GrowGarden`), `ElytrixPlaceholders.jar` (`SmilePlaceholders`), `TAB v5.5.0.jar`, `Vault-1.7.3.jar`, `multiverse-core-4.3.16.jar`, `nKits-1.jar`.

### В. Очистка базы данных `LuckPerms` от вшитых админок (`*`)
В локальной базе `LuckPerms/luckperms-h2-v2.mv.db` были заранее прописаны **9 чужих аккаунтов с полными правами `*`, группой `admin` и ключами веб-редактора (`lp-editor-key`)** (`w3t1k`, `kondr_ms`, `flok1_1337`, `h0seek`, `imilpro1234` и др.).
- Через H2 JDBC полностью очищены таблицы пользователей (`luckperms_user_permissions`, `luckperms_players`, `luckperms_actions`) с последующим `SHUTDOWN COMPACT`.
- **Все донат-группы, префиксы, веса и права групп сохранены на 100%.**
- Также очищены старые профили игроков `Essentials/userdata/`, логи `TAB/*.log`, кэш `.paper-remapped/` и временные `.dll` библиотеки `RoseGarden/tmp/`.

---

## 2. Полный ребрендинг на **Elytrix** и смена палитры (`&#F8BEFB` + `&f`)

### Контакты и ссылки проекта (прописаны везде)
- **Название сервера:** `Elytrix` (подписка `RwPlus` / `RW+` → `ElytrixPlus` / `EL+`)
- **Сайт:** `https://elytrix.pw` (`elytrix.pw` в компактных строках скорборда)
- **IP:** `mc.Elytrix.pw`
- **Discord:** `dsc.gg/elytrix`
- **Telegram:** `t.me/elytrix_ru`
- **Валюта и механики:** `риллики` / `рилликов`, ромашки, осколки, киты, кейсы, зачарования и все игровые механики оставлены нетронутыми.

### Цветовая палитра
- Вся старая жёлто-оранжевая гамма (`&6`, `&e`, `§6`, `§e`, `#fabc00`, `#f85a28`, `#FFAA00`, `#FB6226`..`#FC771D` и т.д.) во всех **158+ конфигах** и внутри кастомных `.jar` плагинов заменена на:
  - **Основной цвет:** `&#F8BEFB` (нежно-розовый; для плагинов без `&#`-парсера использован нативный Spigot-формат `&x&F&8&B&E&F&B`, который отображает тот же `#F8BEFB`)
  - **Акцентный цвет:** `&f` (белый)
  - **Мягкие розово-белые градиенты:** `<#F8BEFB>...</#FFFFFF>` и `#F8BEFB` → `#FAD8FC` в `TAB`, скорборде, автосообщениях `CakeChat`, голограммах `DecentHolograms` и меню `DeluxeMenus`.
- Декоративные оранжевые стеклянные панели в GUI (`CakeReports`, `TradeSystem`) заменены на `PINK_STAINED_GLASS_PANE`, цвета BossBar `YELLOW` → `PINK`.

### Переименованные кастомные плагины и плейсхолдеры (`Elytrix*`)
Все 22 плагина с названиями `Smile*` / `Really*` / `Rw*` / `RW*` переименованы (файлы `.jar`, `plugin.yml`, папки конфигов и внутренние сообщения):
- `ElytrixPlaceholders.jar` (`%elytrix_nameserver%`, `%elytrix_site%`, `%elytrix_site_short%`, `%elytrix_ip%`, `%elytrix_discord%`, `%elytrix_tg%`, `%elytrix_playtime_*%`, `%elytrix_ping%`)
- `ElytrixDealer.jar`, `ElytrixOskolki.jar` (`%elytrixoskolki_amount%`), `ElytrixRandomEgg.jar`
- `ElytrixTops.jar` (`%elytrixtops_*%`), `ElytrixELO.jar` (`%elytrixelo_*%`), `ElytrixPlHide.jar`
- `ElytrixAir.jar`, `ElytrixBoss.jar`, `ElytrixCheck.jar`, `ElytrixClock.jar`, `ElytrixContest.jar`, `ElytrixContracts.jar`, `ElytrixCooldowns.jar`, `ElytrixCrafts.jar`, `ElytrixGranter.jar`, `ElytrixGrowGarden.jar`, `ElytrixItems.jar`, `ElytrixKiller.jar`, `ElytrixPortals.jar`, `ElytrixSiege.jar`, `ElytrixStaffWork.jar`
- Добавлены удобные команды: `/elytrix` (меню бесплатных наград), `/site`, `/ds`, `/tg`.

### Обновлённый Ресурспак (`Elytrix-RP-1.21.zip`)
- **`logotype.png` (меню паузы `ESC`):** перерисован пиксель-арт логотип **`ELYTRIX`** в бело-розовом стиле (`#FFFFFF` + `#F8BEFB`) поверх обновлённого розово-тёмного щита со скрещёнными мечами.
- **`gui_bg.png` (главная рамка меню):** оранжевый корпус полностью перекрашен в пастельно-розовый `#F8BEFB`, а верхний герб **`RW`** заменён на пиксель-арт **`EL`**.
- **`title_00.png` и `title_11.png`:** заголовок меню **`RW+`** перерисован в **`EL+`** идентичным пиксельным шрифтом.
- **Все 50+ жёлто-оранжевых UI-текстур** (`gui_bg_2.png`, `gui_bg_9.png`, `bar/*.png`, карточки разделов `content_*.png`, навигационные иконки меню) переведены в палитру `#F8BEFB` + белый акцент.
- **`pack.png`** (розовая иконка `ELYTRIX`) сохранён, `pack.mcmeta` обновлён под `Elytrix 1.21 | mc.Elytrix.pw`.
- Сразу упакован в готовый `.zip` формат (`Elytrix-RP-1.21.zip`), который Minecraft 1.21 читает напрямую без перепаковки из `.rar`.

---

## 3. Как скачать и установить

1. Скачайте из ветки/PR репозитория файлы:
   - `Elytrix-1.21-Plugins.zip.001` (~60 МБ)
   - `Elytrix-1.21-Plugins.zip.002` (~54 МБ)
   - `СОБРАТЬ_СБОРКУ.bat`
   - `Elytrix-RP-1.21.zip` (~7.4 МБ — готовый ресурспак)
2. Положите `.001`, `.002` и `СОБРАТЬ_СБОРКУ.bat` в одну папку и запустите **`СОБРАТЬ_СБОРКУ.bat`** — за 2 секунды появится готовый архив `Elytrix-1.21-Plugins.zip` (SHA-256: `0eb8e51ef6a78dd624a1d17b3b49fc9dfa52821533487805cf661276d5774751`).
3. Распакуйте папку `plugins` из `ELYTRIX 1.21 — GRIEF` в корень вашего сервера Paper/Purpur 1.21, а `Elytrix-RP-1.21.zip` установите клиентам или подключите в `server.properties` (`resource-pack=`).
