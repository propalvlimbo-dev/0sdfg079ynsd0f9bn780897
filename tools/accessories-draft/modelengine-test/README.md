# Изолированный тест черновой модели

`JAVA=/path/to/java ECJ=/path/to/ecj.jar sh tools/accessories-draft/modelengine-test/run.sh` запускает проверки с ModelEngine 4.1.0 из репозитория (SHA-256 `d24b7d4e865f5453cb2947ec87bd3549e571c7d7927cd22e0c6927b03426090d`). Временный classpath автоматически удаляется; JAR и серверные файлы не изменяются.

Реальные `BlockbenchDeserializer`, `populateBlueprint` и `populateAssets` выполняются при заглушках API, генератора и Bukkit: 4 item-модели, 14 элементов, одна текстура, `idle`, собранных предупреждений нет. Во временной копии `TMath` отключена инициализация через Bukkit; парсер не патчится. Базовый запуск проверяет `Use-New-Rotation=true` на stub fastutil.

Дополнительно при `FASTUTIL=/path/fastutil.jar:/path/slf4j-api.jar` запускается реальный `RotationSolver` при `Use-New-Rotation=false`, как в Git-копии конфига. Проверено с fastutil 8.5.12, скомпилированным из официальных исходников; SLF4J без провайдера. С `MODEL_OUTPUT=/tmp/new-dir` второй запуск экспортирует модели и отдельные item JSON в новую тестовую директорию (только для модели, у которой по одному generated model на bone). `staging-assets` в `tools/accessories-integration` созданы таким способом; текстура и иконка добавлены отдельно.

Ограничения: многие API остаются заглушками, behavior parsers пропущены. Генерация полных ресурспаков, регистрация blueprint на сервере, игровой рендер и привязка к игроку не проверены. Конфигурация live может отличаться. Это не установка и не доказательство игровой работоспособности.
