# Ассеты аксессуаров: модель щупалец Канэки и заголовок меню

Инструменты, которые делают ресурсы для `/аксессуары` **тем же кодом**, что и живой
сервер, и **без нейрослопа**: только пиксель-арт, сгенерированный Python/Pillow, и
настоящий парсер `ModelEngine 4.1.0`.

## Что здесь лежит

| Файл | Назначение |
| --- | --- |
| `build_tentacles.py` | Собирает `elytrix_kaneki_tentacles.bbmodel` и текстуру 64×64 |
| `elytrix_kaneki_tentacles.bbmodel` | Готовый blueprint (4 щупальца, 8 костей, 82 сегмента) |
| `assets/` | JSON и текстура, сгенерированные настоящим ModelEngine |
| `generate_assets.sh`, `GenerateAssets.java` | Запуск генератора ModelEngine офлайн |
| `compose_title.py`, `test_title.py` | Заголовок «АКСЕССУАРЫ» настоящим шрифтом пака |
| `merge_pack.py` | Слияние ассетов в `Elytrix-RP-1.21.zip` |
| `build_package.py` | Сборка ZIP для VDS (RP + blueprint + assets + конфиг) |
| `test_model.py` | Тесты blueprint, ассетов и итогового пака |
| `tentacles_preview.png`, `title_preview.png` | Схематичные превью (НЕ игровой рендер) |

## Модель щупалец

Референс — четыре органических отростка: мясистый корень, большая открытая дуга и
заострённый кончик с чешуйками. ModelEngine 4.1.0 при `Use-New-Rotation: false`
разрешает у куба только одну ось вращения и углы, кратные 22.5°, поэтому каждая
кривая собирается из коротких перекрывающихся сегментов: направление каждого
округляется до 22.5°, а поворот больше 45° «складывается» перестановкой длины и
ширины куба (повёрнутый на 90° куб — тот же куб). Получается гранёная, но плавная
форма вместо прежнего зигзага.

Важные решения:

* **Две кости на щупальце.** `JavaItemModel.scaleToFit()` в ModelEngine уменьшает
  детализацию вдвое, если куб отстоит от pivot кости дальше 24 единиц. На
  предыдущей модели это обнуляло всю работу. Теперь каждое щупальце — `*_a` + `*_b`,
  максимум 20.5 единицы от pivot, проверено тестом `test_no_bone_is_scaled_down`.
* **Объём в текстуре.** ItemDisplay освещается плоско, поэтому освещение «запечено»
  в тайлы: верхняя грань светлая, бока средние, низ тёмный. Анимация — общий мягкий
  наклон и отставание кончика, чтобы не было лаг-рывков при поворотах.
* **Толщина.** Корень 5.3–5.5 единицы, кончик 1.5–1.6; глубина по Z 3.7–3.9 → 1.15.
  Щупальца начинаются на 1.5–2.3 единицы позади спины и не входят в корпус.

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

    # 2. JSON настоящим ModelEngine (нужны java и ecj)
    JAVA=/path/java ECJ=/path/ecj.jar \
    sh tools/accessories-model/generate_assets.sh \
        tools/accessories-model/elytrix_kaneki_tentacles.bbmodel /tmp/kaneki-assets

    # 3. слияние в копию пака (никогда не правит rp/ на месте)
    python3 tools/accessories-model/merge_pack.py rp/Elytrix-RP-1.21.zip /tmp/new.zip \
        --assets /tmp/kaneki-assets \
        --title tools/accessories-integration/staging-assets/assets/reallyworld/textures/gui/title/elytrix_accessories.png \
        --texture /tmp/kaneki/elytrix_kaneki_tentacles.png

    # 4. готовый ZIP для VDS
    python3 tools/accessories-model/build_package.py elytrix-tentacles-v3.zip

Тесты:

    python3 tools/accessories-model/test_model.py --pack=/tmp/new.zip
    python3 tools/accessories-model/test_title.py

## Ограничения

* Превью — плоская схема (`tentacles_preview.png`), а не скриншот из игры. Игровой
  рендер, анимацию, F5 и вид от других игроков нужно подтверждать на сервере.
* Заглушки `stubs/` (Bukkit, fastutil, slf4j) используются только при офлайн-генерации
  и не попадают ни в плагин, ни в ресурспак.
* Скрипт слияния не трогает `pack.png`, `leather_horse_armor`, атласы и шейдеры,
  но перед установкой всё равно нужен бэкап сервера.
