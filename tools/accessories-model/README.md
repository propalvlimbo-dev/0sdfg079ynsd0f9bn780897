# Ассеты аксессуаров: генерация модели и заголовок меню

Здесь лежат инструменты, которые делают ресурсы для `/аксессуары` **тем же кодом**,
что и живой сервер, и рисуют заголовок меню настоящим шрифтом текстурпака.

## `compose_title.py` — заголовок «АКСЕССУАРЫ»

Заголовки всех меню (`МЕНЮ`, `ДОНАТ`, `ВАРПЫ`, …) — это ячейки 128×32 в
`assets/reallyworld/textures/gui/title/title_00.png`. Скрипт вырезает из этого
атласа сами буквы, раскладывает слово с тем же шагом 1 px, той же высотой
заглавных 6 px и тем же базовым рядом 18–23, что и остальные заголовки, и
сохраняет новый файл `assets/reallyworld/textures/gui/title/elytrix_accessories.png`.

Раньше этот файл был нарисован отдельным самодельным шрифтом и слово было сжато
до 50 px — поэтому в игре «АКСЕССУАРЫ» выглядело сплюснутым и не совпадало с
остальными меню. Теперь слово занимает 62 px, буквы пиксель-в-пиксель совпадают
с `title_00.png`, а верхние 3 ряда букв светлее нижних 3 — как у всего пака.

Только пиксель-арт, без генерации ИИ и без сторонних изображений.

    python3 tools/accessories-model/compose_title.py \
        title_00.png \
        tools/accessories-integration/staging-assets/assets/reallyworld/textures/gui/title/elytrix_accessories.png

Проверки (формат, базовый ряд, совпадение букв с атласом, цвета, метрики
провайдера шрифта после слияния пака):

    python3 tools/accessories-model/test_title.py

## `generate_assets.sh` — JSON модели ресурспака

Запускает **настоящий** `BlockbenchDeserializer` + `BlockbenchParser.populateBlueprint`
и `populateAssets` из `plugins/ModelEngine-4.1.0.jar` с `Use-New-Rotation=false`
(как в `plugins/ModelEngine/config.yml`), но с заглушками Bukkit/fastutil/slf4j из
`stubs/`. На выходе — ровно те `assets/modelengine/items|models/<модель>/*.json`,
которые ModelEngine генерирует сам; файлы можно класть в `Elytrix-RP-1.21.zip`
без изменений.

    JAVA=/path/to/java ECJ=/path/to/ecj.jar \
    sh tools/accessories-model/generate_assets.sh \
        tools/accessories-model/elytrix_kaneki_tentacles.bbmodel /tmp/kaneki-assets

Скрипт никогда не пишет в `plugins/` и `rp/` и не запускается, если каталог
вывода уже существует. Заглушки не попадают ни в плагин, ни в ресурспак — это
только среда тестирования.

Проверено: для модели из `tools/accessories-draft/elytrix_kaneki_tentacles.bbmodel`
скрипт выдаёт файлы, **байт-в-байт** совпадающие с `staging-assets` пакета v2,
которые раньше были сгенерированы отдельной веткой тестов.

## Ограничения

- Это не установка и не доказательство игрового рендера: клиентский вид нужно
  подтверждать скриншотом в игре.
- Заглушки fastutil повторяют только использованные ModelEngine сигнатуры;
  при обновлении ModelEngine список стоит перепроверить запуском скрипта.
- `stubs/` — тестовый код, в серверные JAR и в ресурспак не попадает.
