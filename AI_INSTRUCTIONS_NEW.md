# ИНСТРУКЦИЯ ДЛЯ ИИ — Elytrix (репозиторий: ресурспак + плагины)

Короткая версия. Проект — Minecraft 1.21.11 (Leaf), сервер в стиле ReallyWorld,
донат-привилегии, кастомные 3D-модели `ModelEngine 4.1.0` и свой ресурспак
`Elytrix-RP-1.21.zip`.

--------------------------------------------------------------------------------
## 1. ЧТО ПРИСЫЛАТЬ, КОГДА ВСЁ СДЕЛАНО
--------------------------------------------------------------------------------
Порядок в КАЖДОМ ходе:

1. Изменил/собрал файлы → **сразу же** `git add -A && git commit && git push origin <ветка>`
   (контейнер может сброситься к базовому коммиту — незапушенное пропадёт).
2. Взять **полный 40-символьный SHA**: `git rev-parse HEAD`.
   ⚠️ НИКОГДА не давать ссылку по имени ветки — `raw.githubusercontent.com`
   кеширует её 5+ минут, и VDS скачает старый архив.
3. Положить готовый архив в корень репозитория и показать его пользователю.
4. В ответе дать **ОДНУ** готовую SSH-команду для VDS (без объяснений, без
   changelog — пользователь не любит лишний текст).

Шаблон команды (пути внутри архива — относительные от корня сервера):

```text
curl -fsSL "https://raw.githubusercontent.com/<OWNER>/<REPO>/<COMMIT_SHA>/<ARCHIVE>.zip" -o /tmp/<ARCHIVE>.zip && unzip -oq /tmp/<ARCHIVE>.zip -d /root/RW_GRIEF && mkdir -p /root/RP && cp -f /root/RW_GRIEF/rp/Elytrix-RP-1.21.zip /root/RP/Elytrix-RP-1.21.zip && chmod 644 /root/RP/Elytrix-RP-1.21.zip && rm -f /tmp/<ARCHIVE>.zip && sha1sum /root/RP/Elytrix-RP-1.21.zip
```

Если менялся ресурспак: после распаковки **обязательно** сверить выведенный
`SHA-1` с тем, что в `plugins/ElytrixRP/config.yml` (там их ровно 2 штуки).

Что написать в конце: `restart` (или `/dm reload` + `/dh reload`, если менялись
только меню/голограммы). DeluxeMenus и DecentHolograms читают конфиги только
при старте.

--------------------------------------------------------------------------------
## 2. ГДЕ ЧТО ЛЕЖИТ НА VDS
--------------------------------------------------------------------------------
| Путь | Что это |
|---|---|
| `/root/RW_GRIEF/` | корень сборки сервера (плагины, `config/`, `start.sh`) |
| `/root/RP/Elytrix-RP-1.21.zip` | раздаваемый ресурспак (порт `:8085`, сайт `elytrix.pw`) |
| `plugins/ElytrixRP/config.yml` | `sha1` ресурспака (2 вхождения) |
| `plugins/ModelEngine/blueprints/*.bbmodel` | исходники 3D-моделей |
| `plugins/ModelEngine/resource pack/` | сгенерированный пак ModelEngine |
| `rp/Elytrix-RP-1.21.zip` | сам ресурспак (в репозитории) |
| `tools/accessories-model/`, `tools/donate-models/` | генераторы моделей и сборщики пака |
| `plugins/nKits/Kits/*.yml` | донат-киты |
| `plugins/DeluxeMenus/gui_menus/` | меню (`/donate`, `/kits`, превью) |
| `plugins/DecentHolograms/holograms/don*.yml` | голограммы с ценами доната |
| `plugins/LuckPerms/` | группы/права. **H2-базу руками НЕ трогать** — только `lp` команды |

Ядро: Leaf `1.21.11`, `DataVersion 4671`, Java 21, в `start.sh` обязателен
`-Dblib.server.version=1.21.10`.

**Запреты:** не убивать порты `:8085` (сайт + раздача РП), `:20559` (API сайта),
`:24454` (войс). Не класть в архивы живые данные: пароли, `owned_accessories.yml`,
`ModelEngine/config.yml`, `.data/`, базы `LuckPerms`/`LiteBans`/`PlayerPoints`/`BCases`.

**Если контейнер сбросился** (в корне нет `plugins/`):
`git fetch origin <ветка> && git reset --hard FETCH_HEAD && git clean -fdx`,
затем в `/tmp/pytools` поставить `pyyaml pillow numpy jdk4py==25.0.2.1` и
`ecj-3.46.100.jar` (из npm `exoproc-jjit`), потому что `javac` в контейнере нет.

--------------------------------------------------------------------------------
## 3. КАК ДЕЛАЮТСЯ МОДЕЛКИ И АНИМАЦИИ
--------------------------------------------------------------------------------
Конвейер полностью программный, без десктопного Blockbench и без запуска сервера.

1. **Генератор** — Python (`Pillow` + `json`), например
   `tools/accessories-model/build_zeus_wings.py`. Он пишет
   `plugins/ModelEngine/blueprints/elytrix_<name>.bbmodel`
   (формат Blockbench `4.10`, `model_format: free`, `box_uv: false`,
   `resolution 16x16`) и рисует текстуру пиксель-артом через PIL.
2. **Разбор в ассеты ModelEngine** —
   `tools/accessories-model/generate_assets.sh <bp.bbmodel> <out>` (настоящий парсер,
   нужен `JAVA` + `ECJ`), результат перепроверяется питоновским
   `build_modelengine_assets.py` — имя костей, координаты и UV должны совпасть
   на 100 %.
3. **Раскладка** — `items/`, `models/` и текстура копируются в
   `plugins/ModelEngine/resource pack/assets/modelengine/` **и** в
   `tools/accessories-model/assets/modelengine/` (два дерева держать синхронно).
4. **Сборка пака** — строго в этом порядке:
   `merge_pack.py` → `patch_rp_fame.py` → `patch_rp_notice_font.py`
   (всё детерминированно: фиксированные даты, сортировка имён).
   После каждого шага пересчитывать `sha1` и прописывать его в
   `plugins/ElytrixRP/config.yml`.
5. **Архив на VDS** — `tools/accessories-model/make_update_zip.py`
   (содержимое `elytrix-freakmodel.zip` + все изменённые конфиги/джарники,
   пути относительные от корня сервера).

**Жёсткие правила моделей:**
- `16 BB = 1 блок`; кость не дальше `±24 BB` от пивота; **0 повёрнутых кубов** —
  наклон/поворот только анимацией (ModelEngine 4.1.0 падает на `RotationSolver`).
- Текстура — процедурная, без «нейрослопа», без полос: только плавный градиент.
- UV строго внутри `0..размер_текстуры`; при отрицательных UV — сортировать и
  клампить.
- Перекрывающиеся сегменты **обязательно** разносить по глубине (иначе
  z-fight: соосные грани с разным UV). Проверять скриптом перед сборкой.
- Анимация — ключевыми кадрами: период, число кадров, скорость; перед сборкой
  проверять габарит по всем кадрам (модель не должна проваливаться под колени
  или улетать за спину).
- Модель донат-предметов (мечи) — это оверрайд `custom_model_data` в
  `assets/minecraft/models/item/netherite_sword.json`, сама модель лежит в
  `assets/reallyworld/models/item/sword/<name>.json` + текстура рядом.
  Следующий свободный CMD — `5016`.
