# Ассеты аксессуаров: модель щупалец Канэки и заголовок меню

Инструменты, которые делают ресурсы для `/аксессуары` **тем же кодом**, что и живой
сервер, и **без нейрослопа**: только пиксель-арт, сгенерированный Python/Pillow, и
настоящий парсер `ModelEngine 4.1.0`.

## Что здесь лежит

| Файл | Назначение |
| --- | --- |
| `build_tentacles.py` | Собирает `elytrix_kaneki_tentacles.bbmodel` и текстуру 64×64 |
| `build_icon.py` | Рисует иконку аксессуара для меню (32×32) и её item-модель |
| `elytrix_kaneki_tentacles.bbmodel` | Готовый blueprint (4 клинка, 24 кости, 48 сегментов) |
| `assets/` | JSON и текстура, сгенерированные настоящим ModelEngine |
| `generate_assets.sh`, `GenerateAssets.java` | Запуск генератора ModelEngine офлайн |
| `compose_title.py`, `test_title.py` | Заголовок «АКСЕССУАРЫ» настоящим шрифтом пака |
| `merge_pack.py` | Слияние ассетов в `Elytrix-RP-1.21.zip` |
| `build_package.py` | Сборка ZIP для VDS (RP + blueprint + assets + конфиг) |
| `test_model.py` | Тесты blueprint, ассетов и итогового пака |
| `result_preview.png` | Рендер по готовым JSON пака (вид со спины, 3/4, сверху) |
| `tentacles_preview.png`, `title_preview.png`, `icon_preview.png` | Схематичные превью (НЕ игровой рендер) |

## Модель щупалец

Референс — четыре длинных тонких красных клинка: выходят из спины и уходят в стороны
и назад длинными плавными дугами, сужаясь в остриё.

Что изменилось в v5 (после игровых скриншотов v4):

* **Толщина.** У v4 сечение было 8–9 единиц в ширину и почти столько же в глубину —
  это читалось как брусок. Теперь 5.2 на корне и 0.26 на кончике (0.16 блока),
  глубина — примерно половина ширины. Пропорция близка к референсу, но мягче.
* **Пила по краю.** У v4 угол куба менялся каждые 2 единицы, а углы куба могут быть
  только кратны 22.5°, поэтому силуэт был ступенчатым. Теперь кривизну несут **кости**
  (у костей нет ограничения на угол — в поставляемых dwarf/goblin моделях стоят
  значения вроде −79.9°), а кубы внутри кости вообще не повёрнуты. Стыки по 4–10°
  вместо зигзага 22.5°.
* **Иерархия.** Кубы задаются в rest-позе вдоль +X, а движок складывает повороты
  parent → child, как в цепочке бедро → голень → стопа у `gp2_goblin_warrior`.
  Поэтому `RotationSolver` (та часть ModelEngine 4.1.0, что падает на углах кубов вне
  сетки 22.5°) вообще не вызывается.
* **Четыре плоскости.** Корневая кость каждого клинка повёрнута по Y на свой угол
  (−24°, −32°, 202°, 209°), поэтому веер не лежит в одной плоскости, как v3.
* **Размер.** Размах ±42 по X, вылет назад до 25 единиц (1.5 блока), высота 14–37.

## Заголовок меню

Заголовки меню пака (`МЕНЮ`, `ДОНАТ`, `ВАРПЫ`, …) — ячейки 128×32 в
`assets/reallyworld/textures/gui/title/title_00.png`. Скрипт вырезает из этого атласа
сами буквы и раскладывает слово «АКСЕССУАРЫ» с тем же шагом 1 px, высотой заглавных
6 px и тем же базовым рядом 18–23. Раньше этот файл рисовался отдельным самодельным
шрифтом и был сжат до 50 px — поэтому слово выглядело сплюснутым. Сейчас 62 px и
буквы пиксель-в-пиксель из пака. Верхние 3 ряда букв светлее нижних 3 — как у всех.

## Сборка

    # 1. модель + текстура
    python3 tools/accessories-model/build_tentacles.py --out-dir /tmp/kaneki --preview

    # 2. иконка для меню
    python3 tools/accessories-model/build_icon.py --out-dir /tmp/icon

    # 3. JSON настоящим ModelEngine (нужны java и ecj)
    JAVA=/path/java ECJ=/path/ecj.jar \
    sh tools/accessories-model/generate_assets.sh \
        /tmp/kaneki/elytrix_kaneki_tentacles.bbmodel /tmp/kaneki-assets

    # 4. общий staging: ассеты модели + иконка меню (reallyworld/...)
    mkdir -p /tmp/stage/assets
    cp -r /tmp/kaneki-assets/assets/* /tmp/stage/assets/
    cp -r /tmp/icon/assets/* /tmp/stage/assets/

    # 5. слияние в копию пака (никогда не правит rp/ на месте)
    python3 tools/accessories-model/merge_pack.py rp/Elytrix-RP-1.21.zip /tmp/new.zip \
        --assets /tmp/stage --allow-existing-glyph \
        --title tools/accessories-integration/staging-assets/assets/reallyworld/textures/gui/title/elytrix_accessories.png \
        --texture /tmp/kaneki/elytrix_kaneki_tentacles.png

    # 6. готовый ZIP для VDS
    python3 tools/accessories-model/build_package.py elytrix-tentacles-v5.zip

Тесты:

    python3 tools/accessories-model/test_model.py --pack=/tmp/new.zip
    python3 tools/accessories-model/test_title.py

## Ограничения

* Превью — плоская схема (`result_preview.png`), а не скриншот из игры. Игровой
  рендер, анимацию, F5 и вид от других игроков нужно подтверждать на сервере.
* `--allow-existing-glyph` нужен, когда исходный пак уже содержит глиф `ꏠ`
  (повторная сборка поверх предыдущей версии).
* У куба одна ось вращения, поэтому у сильно закрученных сегментов остаётся
  отклонение до ~0.4 по нормали к плоскости наклона — это «гранёность» Minecraft,
  а не дыра в геометрии.
* Заглушки `stubs/` (Bukkit, fastutil, slf4j) используются только при офлайн-генерации
  и не попадают ни в плагин, ни в ресурспак.
* Скрипт слияния не трогает `pack.png`, `leather_horse_armor`, атласы и шейдеры,
  но перед установкой всё равно нужен бэкап сервера.
